"""Citation Firewall as a graph step: verify the shortlist and the adverse authorities (FR-07, FR-08)."""

from __future__ import annotations

from stare.agents.base import AgentResult, BaseAgent
from stare.agents.state import ResearchState, dump, load_authorities
from stare.schemas import Authority, AuthorityRank, CitationCheck

FLAGGED = "Gate 4 warning: not used until reviewed by the attorney"


def summarize_checks(checks: list[CitationCheck]) -> str:
    counts = {s: sum(c.status == s for c in checks) for s in ("verified", "warning", "blocked", "unresolved")}
    parts = [f"{n} {s}" for s, n in counts.items() if n]
    return f"{len(checks)} checked: " + ", ".join(parts) if checks else "0 citations checked"


def gate4_warned(check: CitationCheck) -> bool:
    return any(g.gate == 4 and g.outcome == "warn" for g in check.gates)


class FirewallAgent(BaseAgent):
    name = "citation_firewall"

    def running_summary(self, state: ResearchState) -> str:
        n = len(state.get("shortlist") or []) + len(state.get("adverse") or [])
        return f"Checking {n} citations through four gates"

    def verify(self, authorities: list[Authority]) -> tuple[list[Authority], list[Authority], list[CitationCheck]]:
        passed, failed, checks = [], [], []
        for a in authorities:
            check = self.deps.firewall.verify_authority(a)
            checks.append(check)
            update: dict = {"verification": check}
            if gate4_warned(check):
                update["rank"] = AuthorityRank(status="flagged", weight=0.0, reason=f"{FLAGGED} ({check.reason})")
            a = a.model_copy(update=update)
            (passed if check.exportable else failed).append(a)
        return passed, failed, checks

    def execute(self, state: ResearchState) -> AgentResult:
        support_ok, support_bad, checks = self.verify(load_authorities(state.get("shortlist")))
        adverse_ok, adverse_bad, adverse_checks = self.verify(load_authorities(state.get("adverse")))
        rejected = list(state.get("rejected") or []) + [
            {"key": a.key, "citation": a.citation, "case_name": a.case_name,
             "reason": a.verification.reason if a.verification else "failed verification"}
            for a in support_bad + adverse_bad
        ]
        all_checks = checks + adverse_checks
        usable = [a for a in support_ok if a.kind == "case" and a.rank and a.rank.status != "flagged"]
        loop = state.get("loop_count", 0)
        retry = len(usable) < self.deps.settings.min_verified_authorities and loop < self.deps.settings.max_research_loops - 1
        summary = summarize_checks(all_checks)
        if retry:
            summary += f"; only {len(usable)} usable authorities, searching again"
        return AgentResult(
            update={
                "verified": dump(support_ok),
                "adverse": dump(adverse_ok),
                "checks": [{"phase": "candidates", **dump(c)} for c in checks]
                + [{"phase": "adverse", **dump(c)} for c in adverse_checks],
                "rejected": rejected,
                "loop_count": loop + 1 if retry else loop,
                "retry_research": retry,
            },
            summary=summary,
            data={s: sum(c.status == s for c in all_checks) for s in ("verified", "warning", "blocked", "unresolved")}
            | {"retry": retry},
        )
