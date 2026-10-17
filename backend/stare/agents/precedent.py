"""Precedent Agent: rank each authority as binding or persuasive for the court of filing (FR-06, Table 26)."""

from __future__ import annotations

import re

from stare.agents.base import AgentResult, BaseAgent
from stare.agents.state import ResearchState, dump, load_authorities, load_case_record
from stare.schemas import Authority, AuthorityRank
from stare.text import majority_text, split_sentences

_STATUTE_RANK = AuthorityRank(status="binding", weight=1.0, reason="Federal statute enacted by Congress; binds every federal court")
_REGULATION_RANK = AuthorityRank(
    status="persuasive", weight=0.7,
    reason="EEOC regulation implementing the statute; courts give it weight but decide the statute's meaning",
)
RELEVANCE_WEIGHT = 0.5  # final_score = 0.5 * retrieval relevance + 0.5 * authority weight

_RULE_CUES = ("must", "hold", "held", "require", "established", "prima facie", "burden", "standard", "means",
              "shall", "therefore", "conclude", "test", "plaintiff", "employer")
_WORD = re.compile(r"[a-z]{3,}")
# Procedural history and party arguments are not statements of the rule.
_HISTORY = re.compile(r"\b(?:district court|court of appeals|the panel|petitioner|respondent|argues|contends|"
                      r"conclude[sd]?|accused|they|has said|have said|some courts|other courts|held:|syllabus|we granted certiorari|the jury|dissent|I would|majority)\b", re.IGNORECASE)
# Sentences that never state a rule: the question presented, the Court declining to reach an issue, a party's
# position, the facts, or what a lower court did. They are excluded outright.
_NOT_A_RULE = re.compile(
    r"\b(?:question (?:presented|is whether|before us|this case presents)|(?:the|this) question|to decide whether|"
    r"we (?:need not|do not) (?:consider|decide|reach|address|reconcile)|need not reconcile|we granted|believe that|"
    r"in support of (?:her|his|their)|\b(?:both |also )?(?:argue|argues|argued|contend|contends|contended|claimed)\b|"
    r"proceeds in (?:two|three|four) steps|^(?:in|on|by) (?:january|february|march|april|may|june|july|august|september|"
    r"october|november|december) \d{4}|^(?:one|another|two|three) (?:claimed|testified|said)|\bwitness|testif|testimony|"
    r"\b(?:district court|courts? of appeals|the panel|the trial court)\b.{0,40}?\b(?:held|excluded|granted|denied|"
    r"concluded|ruled|reasoned|found|dismissed|affirmed|reversed)\b|"
    r"sought to|having determined|it is plain that the court|on that assumption|did not settle|"
    r"(?:petitioner|respondent|plaintiff|young|the government)s? (?:argues?|contends?|claims?|asserts?))\b|\?$",
    re.IGNORECASE,
)
# Quoted sentences must not themselves contain citations: the Firewall would read them as this memo's own cites.
_EMBEDDED_CITE = re.compile(
    r"\b\d{1,4}\s+(?:U\.\s?S\.|S\.\s?Ct\.|L\.\s?Ed|F\.\s?(?:2d|3d|4th|Supp|App)|F\.\s+\d)|\bU\.S\.C\.|C\.F\.R\.|\b[Ii]d\.|§"
)


def _quotable(s: str) -> bool:
    return not (not 60 <= len(s) <= 320 or not s[0].isupper() or re.search(r"\(\d{4}\)", s) or _NOT_A_RULE.search(s)
                or s.count('"') % 2 or " v. " in s or _EMBEDDED_CITE.search(s)
                or s.lower().startswith(("see ", "id.", "cf.")))


_LEAD_JUNK = re.compile(r"^(?:(?:Ibid|Id)\.\s+)+|^.*?\.\s+\d{1,3}\s+[IVX]+(?:\s+[A-Z])?\s+(?=[A-Z])")


def _clean(s: str) -> str:
    """Drop a leading 'Ibid.' / 'Id.' or a footnote-number + section-heading run ("... we agree. 15 III We hold")
    so the quotation starts at the sentence that states the rule; what remains is still verbatim."""
    return _LEAD_JUNK.sub("", s).strip()


def pick_quote(a: Authority, focus: str, opinion_text: str | None = None) -> str:
    """Choose a short, rule-stating sentence to quote verbatim from the opinion of the court. Sentences in the
    retrieved passages get a relevance bonus; with `opinion_text` the whole majority opinion is considered, so
    the holding can be quoted even when retrieval matched a nearby paragraph."""
    focus_terms = set(_WORD.findall(focus.lower()))
    candidates: dict[str, float] = {}
    for passage in a.passages[:3]:
        if passage.part != "majority":
            continue  # never quote a dissent or concurrence as the court's holding
        for s in split_sentences(majority_text(passage.text)):
            candidates[_clean(s)] = 0.25
    if opinion_text:
        for s in split_sentences(majority_text(opinion_text)):
            candidates.setdefault(_clean(s), 0.0)
    best, best_score = "", 0.0
    for s, bonus in candidates.items():
        if not _quotable(s):
            continue
        low = s.lower()
        terms = set(_WORD.findall(low))
        score = bonus + len(terms & focus_terms) / (1 + len(focus_terms)) + 0.15 * sum(c in low for c in _RULE_CUES)
        score += 0.45 * bool(re.search(r"\bwe (?:hold|conclude)\b|\bmust (?:show|prove|establish|demonstrate)\b", low))
        score -= 0.4 * len(_HISTORY.findall(s))
        if score > best_score:
            best, best_score = s, score
    return best


def opinion_text(deps, a: Authority) -> str | None:
    if a.opinion_id is None:
        return None
    from stare.db.models import Opinion

    with deps.session_factory() as session:
        op = session.get(Opinion, a.opinion_id)
        return op.plain_text if op else None


class PrecedentAgent(BaseAgent):
    name = "precedent"

    def running_summary(self, state: ResearchState) -> str:
        return f"Ranking {len(state.get('candidates') or [])} authorities by court hierarchy"

    def rank(self, authorities: list[Authority], filing_court: str | None) -> list[Authority]:
        ranked: list[Authority] = []
        for a in authorities:
            if a.kind == "statute":
                rank = _STATUTE_RANK
            elif a.kind == "regulation":
                rank = _REGULATION_RANK
            else:
                rank = self.deps.ranker.rank(a.court_id, filing_court, published=a.published)
            score = RELEVANCE_WEIGHT * a.relevance + (1 - RELEVANCE_WEIGHT) * rank.weight
            ranked.append(a.model_copy(update={"rank": rank, "final_score": round(score, 4)}))
        return sorted(ranked, key=lambda a: a.final_score, reverse=True)

    def shortlist(self, ranked: list[Authority], size: int) -> list[Authority]:
        """Best authorities overall, but every plan item keeps its top cases and its top statute."""
        chosen: dict[str, Authority] = {}
        items = {a.plan_item_id for a in ranked}
        for item in items:
            mine = [a for a in ranked if a.plan_item_id == item]
            for a in [x for x in mine if x.kind == "case"][:3] + [x for x in mine if x.kind != "case"][:1]:
                chosen.setdefault(a.key, a)
        for a in ranked:
            if len([x for x in chosen.values() if x.kind == "case"]) >= size:
                break
            chosen.setdefault(a.key, a)
        return sorted(chosen.values(), key=lambda a: a.final_score, reverse=True)

    def execute(self, state: ResearchState) -> AgentResult:
        record = load_case_record(state)
        filing = record.court_id
        ranked = self.rank(load_authorities(state.get("candidates")), filing)
        shortlist = [
            a.model_copy(update={"quote": a.quote or (
                pick_quote(a, a.proposition, opinion_text(self.deps, a)) if a.kind == "case" else "")})
            for a in self.shortlist(ranked, self.deps.settings.shortlist_size)
        ]
        binding = sum(1 for a in shortlist if a.rank and a.rank.status == "binding")
        court = self.deps.hierarchy.get(filing).short_name if filing and self.deps.hierarchy.get(filing) else "the court"
        return AgentResult(
            update={"shortlist": dump(shortlist)},
            summary=f"Ranked for {court}: {binding} binding, {len(shortlist) - binding} persuasive (shortlist of {len(shortlist)})",
            data={"binding": binding, "persuasive": len(shortlist) - binding, "court_id": filing},
        )
