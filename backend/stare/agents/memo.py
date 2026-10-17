"""Memo Agent: draft an IRAC memo from verified authority only (FR-09).

Offline mode drafts extractively: rules are stated through verbatim quotations of verified passages, and
the application section maps each element to the closest allegations in the redacted complaint, which
leaves the legal judgement to the attorney. LLM mode writes prose but must cite only the numbered,
verified authorities. Either way, the memo is checked again by the Firewall before the attorney sees it.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from stare import DISCLAIMER
from stare.agents.base import AgentResult, BaseAgent
from stare.agents.state import ResearchState, dump, load_authorities, load_case_record, load_checks, load_plan
from stare.courts.hierarchy import CourtHierarchy
from stare.intake.elements import STATUTE_LABEL
from stare.llm.base import LLMError
from stare.schemas import Authority, CaseRecord, Memo, MemoCitation, ResearchPlan
from stare.text import split_sentences

_WORD = re.compile(r"[a-z]{4,}")
MAX_CASES_PER_ITEM = 3


def bluebook(a: Authority, hierarchy: CourtHierarchy) -> str:
    """'McDonnell Douglas Corp. v. Green, 411 U.S. 792 (1973)' / '42 U.S.C. § 2000e-3'."""
    if a.kind != "case":
        return a.citation
    court = hierarchy.get(a.court_id) if a.court_id else None
    paren = " ".join(x for x in ((court.short_name if court and court.level != "supreme" else ""), str(a.year or "")) if x)
    return f"{a.case_name}, {a.citation}" + (f" ({paren})" if paren else "")


def _warning_line(a: Authority) -> str:
    """'Case, cite: reason', plus Gate 4 treatment only when the reason does not already list it."""
    v = a.verification
    reason = v.reason if v else ""
    extra = [t for t in (v.treatment if v else []) if t not in reason]
    return f"{a.case_name or a.citation}, {a.citation}: {reason}".strip() + (f" ({'; '.join(extra)})" if extra else "")


class _Draft(BaseModel):
    issue: str
    rule: str
    application: str
    conclusion: str


_SYSTEM = (
    "You are a careful US employment-law associate writing an internal IRAC research memo for a supervising attorney. "
    "Use ONLY the numbered authorities provided. Cite each one exactly as given, followed by its marker, e.g. "
    "'McDonnell Douglas Corp. v. Green, 411 U.S. 792 (1973) [1]'. Quote only text that appears verbatim in the "
    "passages provided. Never cite any other case or statute. Flag uncertainty instead of guessing. "
    "Do not give advice addressed to the client; this is research for a lawyer."
)


class MemoAgent(BaseAgent):
    name = "memo"

    def running_summary(self, state: ResearchState) -> str:
        return "Drafting the IRAC memo from verified authorities" + (" (attorney changes)" if state.get("memo_feedback") else "")

    def execute(self, state: ResearchState) -> AgentResult:
        record = load_case_record(state)
        plan = load_plan(state)
        verified = load_authorities(state.get("verified"))
        adverse = load_authorities(state.get("adverse"))
        support = [a for a in verified if not (a.rank and a.rank.status == "flagged")]
        flagged = [a for a in verified if a.rank and a.rank.status == "flagged"]

        markers: dict[str, MemoCitation] = {}

        def cite(a: Authority) -> str:
            if a.key not in markers:
                markers[a.key] = MemoCitation(
                    marker=f"[{len(markers) + 1}]", citation=a.citation, case_name=a.case_name, url=a.url,
                    authority_key=a.key, status=a.verification.status if a.verification else "verified",
                )
            return f"{bluebook(a, self.deps.hierarchy)} {markers[a.key].marker}"

        draft: _Draft | None = None
        if not self.llm.is_offline:
            draft = self._llm_draft(record, plan, support, state, cite)
        if draft is None:
            draft = self._offline_draft(record, plan, support, state, cite)

        adverse_text = self._adverse_section(adverse, state.get("procedural_flags") or [], cite)
        warnings = [_warning_line(a) for a in flagged + [a for a in verified + adverse if a.verification
                                                          and a.verification.status == "warning" and a not in flagged]]
        removed = [
            f"{c.citation.raw or c.citation.cite}: {c.reason}"
            for c in load_checks(state.get("checks")) if not c.exportable
        ]
        claims = ", ".join(sorted({STATUTE_LABEL[c.statute] for c in record.claims})) or "Employment claims"
        memo = Memo(
            title=f"Research Memorandum: {claims}",
            question_presented=plan.question,
            issue=draft.issue,
            rule=draft.rule,
            application=draft.application,
            conclusion=draft.conclusion,
            adverse_authority=adverse_text,
            warnings=list(dict.fromkeys(warnings)),
            citations=list(markers.values()),
            removed_citations=removed,
            disclaimer=DISCLAIMER,
            generated_by=self.llm.name,
        )
        return AgentResult(
            update={"memo": dump(memo), "memo_feedback": "", "status": "researching"},
            summary=f"Drafted IRAC memo with {len(markers)} linked citations, {len(warnings)} warnings",
            data={"citations": len(markers), "warnings": len(warnings), "removed": len(removed)},
        )

    # ------------------------------------------------------------------------------------------ offline

    def _offline_draft(self, record: CaseRecord, plan: ResearchPlan, support: list[Authority], state, cite) -> _Draft:
        items = [i for i in plan.items if i.checked]
        side = "plaintiff" if record.client_side == "plaintiff" else "defendant"
        court = record.court_name or record.court_id or "the court of filing"
        issue = "\n".join(
            [f"Whether the {side}'s claims can be established in {court}, element by element:"]
            + [f"- {i.issue}" for i in items]
        )

        rule_parts: list[str] = []
        for item in items:
            mine = [a for a in support if a.plan_item_id == item.id]
            if not mine:
                rule_parts.append(f"**{item.issue}.** No verified authority was found for this issue; further research is needed.")
                continue
            sentences = [f"**{item.issue}.**"]
            for a in [x for x in mine if x.kind == "statute"][:2]:
                sentences.append(f"The governing provision is {cite(a)}.")
            for a in [x for x in mine if x.kind == "regulation"][:1]:
                sentences.append(f"The implementing regulation is {cite(a)}.")
            cases = [x for x in mine if x.kind == "case"]
            for a in cases[:MAX_CASES_PER_ITEM]:
                weight = a.rank.reason if a.rank else ""
                if a.quote:
                    # the weight goes before the quotation, so each authority stays one sentence for the Firewall
                    end = "" if a.quote.rstrip()[-1:] in ".?!" else "."
                    sentences.append(f'In {cite(a)} ({weight}), the court explained: "{a.quote}"{end}')
                else:
                    sentences.append(f"See {cite(a)} ({weight}).")
            rule_parts.append(" ".join(sentences))
        rule = "\n\n".join(rule_parts)

        facts = state.get("redacted_text") or record.facts_summary
        app_parts = [f"The complaint alleges, in summary: {record.facts_summary.strip()}" if record.facts_summary else ""]
        for item in items:
            lines = [f"**{item.issue}**"]
            for element in item.elements:
                allegation = self._closest_allegation(element, facts)
                lines.append(f"- {element}: " + (f"the complaint alleges: '{allegation}'" if allegation
                                                  else "no specific allegation found; the attorney should confirm the facts"))
            app_parts.append("\n".join(lines))
        for flag in state.get("procedural_flags") or []:
            app_parts.append(f"- Timeliness: {flag}")
        application = "\n\n".join(p for p in app_parts if p)

        binding = sum(1 for a in support if a.rank and a.rank.status == "binding")
        conclusion = (
            f"The research identified {len(support)} verified authorities ({binding} binding in {court}) addressing "
            f"{len(items)} issues. Each element above should be assessed against the cited rules, together with the "
            "adverse authority listed below, which must be distinguished or disclosed as required by Model Rule 3.3. "
            "This draft was assembled extractively from verified sources; legal conclusions are for the attorney."
        )
        if state.get("memo_feedback"):
            conclusion += f"\n\nAttorney instruction recorded for revision: {state['memo_feedback']}"
        return _Draft(issue=issue, rule=rule, application=application, conclusion=conclusion)

    @staticmethod
    def _closest_allegation(element: str, text: str) -> str:
        terms = set(_WORD.findall(element.lower()))
        best, best_score = "", 0
        for sentence in split_sentences(text):
            if not 25 <= len(sentence) <= 400:
                continue
            score = len(terms & set(_WORD.findall(sentence.lower())))
            if score > best_score:
                best, best_score = re.sub(r"\s+\d{1,3}$", "", sentence.strip().rstrip(".")), score
        return best.replace('"', "") if best_score >= 2 else ""

    # ------------------------------------------------------------------------------------------ LLM

    def _llm_draft(self, record: CaseRecord, plan: ResearchPlan, support: list[Authority], state, cite) -> _Draft | None:
        catalogue = []
        for a in support:
            ref = cite(a)
            passages = "\n".join(f"    > {p.text}" for p in a.passages[:2])
            catalogue.append(f"{ref} — {a.rank.reason if a.rank else ''}; issue {a.plan_item_id}\n{passages}")
        prompt = (
            f"Case record (redacted):\n{record.model_dump_json(include={'court_name', 'claims', 'key_dates', 'facts_summary', 'client_side'})}\n\n"
            f"Research plan:\n{plan.model_dump_json(include={'question', 'items', 'instructions'})}\n\n"
            f"Procedural flags: {state.get('procedural_flags') or []}\n\n"
            "Verified authorities (cite exactly as written, with the marker):\n" + "\n\n".join(catalogue)
        )
        if state.get("memo_feedback"):
            prompt += f"\n\nThe attorney asked for these changes to the previous draft: {state['memo_feedback']}"
        try:
            return self.llm.complete_json(_SYSTEM, prompt, _Draft, tier="main", max_tokens=self.deps.settings.llm_max_tokens)
        except LLMError:
            return None

    # ------------------------------------------------------------------------------------------ adverse

    @staticmethod
    def _adverse_section(adverse: list[Authority], flags: list[str], cite) -> str:
        if not adverse and not flags:
            return "The Opposing Counsel Agent found no adverse authority in the index."
        lines = []
        for a in adverse:
            status = a.rank.status if a.rank else "persuasive"
            quote = f': "{a.quote}"' if a.quote else ""
            end = "" if quote and a.quote.rstrip()[-1:] in ".?!" else "."
            lines.append(f"- {cite(a)} ({status}){quote}{end} {a.adverse_reason}")
        lines += [f"- Procedural risk: {f}" for f in flags]
        return "\n".join(lines)
