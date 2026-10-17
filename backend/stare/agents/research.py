"""Research Agent: one query per legal element, hybrid search, RAG-Fusion (FR-05)."""

from __future__ import annotations

import re

from pydantic import BaseModel
from sqlalchemy import select

from stare.agents.base import AgentResult, BaseAgent
from stare.agents.state import ResearchState, dump, load_plan
from stare.intake.elements import PROCEDURAL, STATUTE_LABEL, THEORIES
from stare.llm.base import LLMError
from stare.db.models import StatuteSection
from stare.schemas import Authority, PlanItem

_SECTION_REF = re.compile(r"§\s*(\d+[a-z]?(?:-\d+)?(?:\.\d+)?)")

# element name -> template queries, across every theory and the procedural items
ELEMENT_QUERIES: dict[str, tuple[str, ...]] = {
    e.name: e.queries for t in THEORIES.values() for e in t.elements
} | {e.name: e.queries for e in PROCEDURAL.values()}


_TERM = re.compile(r"[a-z]{4,}")
_GENERIC = {"title", "claim", "claims", "elements", "employment", "employer", "under", "with", "that", "this",
            "court", "civil", "rights", "action", "plaintiff", "defendant", "requirements"}


_STATUTE_TERMS = {
    "title_vii": re.compile(r"title\s+vii|2000e|pregnancy discrimination act", re.I),
    "ada": re.compile(r"\bADA\b|disabilit|americans with disabilities|1210\d|1211\d|1630", re.I),
    "adea": re.compile(r"\bADEA\b|age discrimination|\b62[1-9]\b|\b63[0-4]\b", re.I),
}


# Passages centred on one of these topics only support plan items about that topic.
_TOPICS = {"retaliat": re.compile(r"\bretaliat", re.I), "pregnan": re.compile(r"\bpregnan", re.I)}


def statute_consistent(a: Authority, item: PlanItem) -> bool:
    """False when the authority's passages discuss other statutes but not the plan item's statute, or are
    centred on retaliation or pregnancy while the plan item is not (those rules differ from the general ones)."""
    raw = " ".join(p.text for p in a.passages[:3])
    mentioned = {st for st, rx in _STATUTE_TERMS.items() if rx.search(raw)}
    if item.statute and mentioned and item.statute not in mentioned:
        return False
    item_text = " ".join([item.issue, *item.elements]).lower()
    for stem, rx in _TOPICS.items():
        if stem not in item_text and len(rx.findall(raw)) >= 2:
            return False
    return True


def best_item(a: Authority, items: list[PlanItem], threshold: float = 0.34) -> PlanItem | None:
    """The plan item whose issue and elements share the most terms with the authority's passages; None when
    nothing matches well (the authority is then kept as a source but not used to state an item's rule)."""
    text = " ".join(p.text for p in a.passages[:3]).lower()
    have = set(_TERM.findall(text))
    best, best_score = None, 0.0
    for item in items:
        if not statute_consistent(a, item):
            continue  # the passage is about a different statute
        want = set(_TERM.findall(" ".join([item.issue, *item.elements]).lower())) - _GENERIC
        if want:
            score = len(want & have) / len(want)
            if score > best_score:
                best, best_score = item, score
    return best if best_score >= threshold else None


class _Queries(BaseModel):
    queries: list[str]


_SYSTEM = (
    "You write search queries for a US federal case-law and statute search engine (BM25 + semantic). "
    "Phrase queries the way courts state the legal rule. Never include case names or citations."
)


class ResearchAgent(BaseAgent):
    name = "research"

    def running_summary(self, state: ResearchState) -> str:
        loop = state.get("loop_count", 0)
        return "Searching statutes and case law" + (f" (retry {loop})" if loop else "")

    def build_queries(self, item: PlanItem, instructions: str, broaden: bool) -> list[tuple[str, str]]:
        """Return (query, element) pairs for one plan item."""
        pairs: list[tuple[str, str]] = [(q, item.issue) for q in item.queries]
        for element in item.elements:
            for q in ELEMENT_QUERIES.get(element, ()):
                pairs.append((q, element))
            if element not in ELEMENT_QUERIES or broaden:
                pairs.append((element, element))
        if broaden and item.statute:
            pairs.append((f"{item.issue} {STATUTE_LABEL[item.statute]}", item.issue))
        if instructions:
            pairs.append((instructions, item.issue))
        if not self.llm.is_offline:
            try:
                extra = self.llm.complete_json(
                    _SYSTEM,
                    f"Issue: {item.issue}\nElements: {item.elements}\nAttorney instruction: {instructions or 'none'}\n"
                    "Write up to two queries per element.",
                    _Queries, tier="fast", max_tokens=1500,
                )
                pairs += [(q, item.issue) for q in extra.queries[: 2 * max(1, len(item.elements))]]
            except LLMError:
                pass
        seen: set[str] = set()
        return [(q, e) for q, e in pairs if not (q.lower() in seen or seen.add(q.lower()))]

    def statute_filter(self, authorities: list[Authority], item: PlanItem) -> list[Authority]:
        """Keep statutes/regulations of the plan item's statute only (no ADA regulation for a Title VII issue),
        and put the section named in the issue itself (e.g. § 2000e-3) first."""
        ids = [a.section_id for a in authorities if a.section_id]
        named = _SECTION_REF.findall(" ".join([item.issue, *item.elements]))
        with self.deps.session_factory() as s:
            statute_of = dict(s.execute(select(StatuteSection.id, StatuteSection.statute)
                                        .where(StatuteSection.id.in_(ids))).all()) if ids else {}
            pinned = [
                Authority(key=f"sec:{sec.id}", kind="regulation" if sec.code == "CFR" else "statute", citation=sec.citation,
                          url=sec.url, section_id=sec.id, relevance=1.0)
                for sec in s.scalars(select(StatuteSection).where(StatuteSection.section.in_(named)))
            ] if named else []
        kept = [a for a in authorities
                if a.section_id is None or not item.statute or statute_of.get(a.section_id) in (None, item.statute)]
        have = {a.key for a in kept}
        return [p for p in pinned if p.key not in have] + kept

    def execute(self, state: ResearchState) -> AgentResult:
        plan = load_plan(state)
        settings = self.deps.settings
        loop = state.get("loop_count", 0)
        rejected = {r.get("key") for r in state.get("rejected") or [] if r.get("key")}
        k = settings.candidates_per_query * (1 + loop)

        by_key: dict[str, Authority] = {}
        n_queries = 0
        for item in plan.items:
            if not item.checked:
                continue
            pairs = self.build_queries(item, plan.instructions, broaden=loop > 0)
            n_queries += len(pairs)
            element_of = {q: e for q, e in pairs}
            chunks = self.deps.retriever.search_many([q for q, _ in pairs], k=k)
            limit = max(8, settings.max_candidates // max(1, len(plan.items)))
            found = self.statute_filter(self.deps.retriever.authorities_from_chunks(chunks, limit=limit), item)
            for a in found:
                if a.key in rejected or (a.kind == "case" and not statute_consistent(a, item)):
                    continue
                best_query = a.passages[0].query if a.passages else ""
                a = a.model_copy(update={"plan_item_id": item.id, "proposition": element_of.get(best_query, item.issue)})
                if a.key not in by_key or a.relevance > by_key[a.key].relevance:
                    by_key[a.key] = a

        # The attorney's own research question (and instruction) is searched directly as well: element
        # templates find the general rules, the question finds the authority on the precise point.
        direct = [q for q in (plan.question, plan.instructions) if q and q.strip()]
        checked = [i for i in plan.items if i.checked]
        if direct and checked:
            n_queries += len(direct)
            chunks = self.deps.retriever.search_many(direct, k=k)
            for a in self.deps.retriever.authorities_from_chunks(chunks, limit=10):
                if a.kind != "case" or a.key in rejected:
                    continue  # statutes stay tied to their plan item (statute_filter)
                if a.key in by_key:
                    prev = by_key[a.key]
                    by_key[a.key] = prev.model_copy(update={"relevance": max(prev.relevance, a.relevance)})
                else:
                    item = best_item(a, checked)
                    by_key[a.key] = a.model_copy(update={
                        "plan_item_id": item.id if item else None,
                        "proposition": item.issue if item else plan.question,
                    })

        candidates = sorted(by_key.values(), key=lambda a: a.relevance, reverse=True)[: settings.max_candidates]
        cases = sum(a.kind == "case" for a in candidates)
        summary = (
            f"Hybrid search: {len(candidates)} candidates ({cases} cases, {len(candidates) - cases} statutes/regulations) "
            f"from {n_queries} queries (BM25 + dense, RRF)"
        )
        return AgentResult(
            update={"candidates": dump(candidates), "status": "researching"},
            summary=summary,
            data={"candidates": len(candidates), "queries": n_queries, "loop": loop},
        )
