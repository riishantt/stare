"""Opposing Counsel Agent: argue the other side and find adverse authority before the memo is drafted (FR-10).

Counter-measure to sycophancy: it is told to search only for authority that hurts the client, including
procedural defences such as a late EEOC charge. Its findings pass through the same Citation Firewall and
are delivered as a separate report that the Memo Agent may not drop (Rule 3.3 duty of candour).
"""

from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel

from stare.agents.base import AgentResult, BaseAgent
from stare.agents.precedent import PrecedentAgent, opinion_text, pick_quote
from stare.agents.state import ResearchState, dump, load_authorities, load_case_record
from stare.intake.elements import PROCEDURAL, theory_for
from stare.llm.base import LLMError
from stare.schemas import Authority, CaseRecord, KeyDate

MAX_ADVERSE = 6
# Language that signals an outcome for the employer: such passages are what opposing counsel would cite.
_DEFENSE_CUES = re.compile(
    r"\b(?:affirm\w*|summary judgment (?:for|in favor of) the (?:employer|defendant)|failed to (?:establish|show|present|raise)|"
    r"no reasonable (?:jury|juror|factfinder)|insufficient|time-barred|untimely|not (?:actionable|materially adverse)|"
    r"did not (?:establish|show)|cannot (?:establish|show|survive)|judgment as a matter of law for|dismiss\w*)\b",
    re.IGNORECASE,
)


class _Counter(BaseModel):
    queries: list[str]


class _Reason(BaseModel):
    reason: str


_SYSTEM = (
    "You are opposing counsel in a US federal employment case. Your job is to find authority and arguments "
    "that hurt the other side's claims: adverse controlling cases, procedural defences, and distinguishing facts. "
    "Never invent case names or citations."
)


def _parse(d: str) -> date | None:
    m = re.match(r"(\d{4})-(\d{2})(?:-(\d{2}))?", d or "")
    if not m:
        return None
    return date(int(m[1]), int(m[2]), int(m[3] or 1))


def _find(dates: list[KeyDate], *words: str) -> date | None:
    for kd in dates:
        if any(w in kd.label.lower() for w in words) and (parsed := _parse(kd.date)):
            return parsed
    return None


def procedural_flags(record: CaseRecord) -> list[str]:
    """Deterministic timeliness checks from the extracted key dates (42 U.S.C. 2000e-5(e)(1), (f)(1))."""
    flags: list[str] = []
    action = _find(record.key_dates, "terminat", "discharg", "fired", "demot", "adverse", "denied")
    charge = _find(record.key_dates, "eeoc", "charge")
    rts = _find(record.key_dates, "right-to-sue", "right to sue", "notice of right")
    filed = _find(record.key_dates, "complaint filed", "suit filed", "filed suit", "lawsuit")
    if action and charge:
        days = (charge - action).days
        if days > 300:
            flags.append(f"EEOC charge filed {days} days after the adverse action: beyond the 300-day limit, "
                         "so discrete-act claims are likely time-barred.")
        elif days > 180:
            flags.append(f"EEOC charge filed {days} days after the adverse action: timely only in a deferral "
                         "state with a state fair-employment agency (300-day limit); confirm the state.")
    if rts and filed and (filed - rts).days > 90:
        flags.append(f"Suit filed {(filed - rts).days} days after the right-to-sue notice: beyond the 90-day limit.")
    if not charge:
        flags.append("No EEOC charge date found: confirm administrative exhaustion before filing.")
    return flags


def _defense_score(a: Authority) -> float:
    return sum(len(_DEFENSE_CUES.findall(p.text)) for p in a.passages[:3]) / 3


class OpposingCounselAgent(BaseAgent):
    name = "opposing_counsel"

    def running_summary(self, state: ResearchState) -> str:
        return "Arguing the other side: searching for adverse authority"

    def counter_queries(self, record: CaseRecord) -> list[str]:
        queries: list[str] = []
        statutes: set[str] = set()
        for claim in record.claims:
            theory = theory_for(claim.statute, claim.theory)
            if theory:
                queries += theory.adverse_queries
                statutes.add(theory.statute)
        for s in statutes:
            queries += PROCEDURAL[s].queries[:2]
        if not self.llm.is_offline:
            try:
                extra = self.llm.complete_json(
                    _SYSTEM,
                    f"Claims and facts (redacted):\n{record.model_dump_json(include={'claims', 'facts_summary', 'key_dates', 'court_name'})}\n"
                    "Write up to six search queries for adverse authority and defences.",
                    _Counter, tier="main", max_tokens=1500,
                )
                queries += extra.queries[:6]
            except LLMError:
                pass
        return list(dict.fromkeys(queries))

    def reason_for(self, a: Authority, query: str, record: CaseRecord) -> str:
        if not self.llm.is_offline:
            try:
                passages = "\n---\n".join(p.text for p in a.passages[:2])
                return self.llm.complete_json(
                    _SYSTEM,
                    f"Client's claims: {[c.model_dump() for c in record.claims]}\nAuthority: {a.case_name or a.citation}\n"
                    f"Passages:\n{passages}\n\nIn two sentences, explain how the defence would use this authority "
                    "against the client, based only on the passages.",
                    _Reason, tier="main", max_tokens=600,
                ).reason
            except LLMError:
                pass
        return f"Defence argument: {query}."

    def execute(self, state: ResearchState) -> AgentResult:
        record = load_case_record(state)
        plan = state.get("plan") or {}
        flags = procedural_flags(record)
        if not plan.get("include_adverse", True):
            return AgentResult(update={"adverse": [], "procedural_flags": flags, "adverse_report": ""},
                               summary="Skipped: the attorney excluded adverse-authority search")

        queries = self.counter_queries(record)
        chunks = self.deps.retriever.search_many(queries, k=self.deps.settings.candidates_per_query)
        found = self.deps.retriever.authorities_from_chunks(chunks, limit=MAX_ADVERSE * 4)
        support = {a.get("key") for a in state.get("shortlist") or []}
        ranked = PrecedentAgent(self.deps).rank(
            [a for a in found if a.kind == "case" and a.key not in support], record.court_id
        )
        ranked.sort(key=lambda a: a.final_score + 0.25 * min(1.0, _defense_score(a)), reverse=True)
        adverse: list[Authority] = []
        for a in ranked[:MAX_ADVERSE]:
            query = a.passages[0].query if a.passages else queries[0]
            adverse.append(a.model_copy(update={
                "adverse": True,
                "adverse_reason": self.reason_for(a, query, record),
                "proposition": query,
                "quote": pick_quote(a, query, opinion_text(self.deps, a)),
            }))
        binding = [a for a in adverse if a.rank and a.rank.status == "binding"]
        circuit = f"{record.circuit}th Cir." if record.circuit and record.circuit.isdigit() else "controlling"
        summary = f"{len(adverse)} adverse authorities ({len(binding)} binding) to disclose or distinguish"
        if flags:
            summary += f"; {len(flags)} procedural flag(s)"
        report = self._report(adverse, flags)
        return AgentResult(
            update={"adverse": dump(adverse), "procedural_flags": flags, "adverse_report": report},
            summary=summary,
            data={"adverse": len(adverse), "binding": len(binding), "flags": flags, "circuit": circuit},
        )

    @staticmethod
    def _report(adverse: list[Authority], flags: list[str]) -> str:
        lines = ["Adverse authority and defences identified by the Opposing Counsel Agent:"]
        for a in adverse:
            status = a.rank.status if a.rank else "persuasive"
            lines.append(f"- {a.case_name or a.citation}, {a.citation} ({status}): {a.adverse_reason}")
        for f in flags:
            lines.append(f"- Procedural: {f}")
        return "\n".join(lines)
