"""Second Firewall pass over the drafted memo text, plus the export check (NFR-01: zero unverified citations)."""

from __future__ import annotations

from stare.agents.base import AgentResult, BaseAgent
from stare.agents.firewall_agent import summarize_checks
from stare.agents.state import ResearchState, dump, load_memo
from stare.schemas import CitationCheck, Memo

# every prose field that is exported (the question presented is editable too, so it is checked like the rest)
MEMO_FIELDS = ("question_presented", "issue", "rule", "application", "conclusion", "adverse_authority")


def check_memo(memo: Memo, firewall) -> tuple[Memo, list[CitationCheck]]:
    """Verify every citation in the memo text, remove sentences whose citations fail, and resync the
    citation list and warnings. Removing a sentence changes its neighbours' context, so the text is
    re-verified until nothing more is removed. Returns the cleaned memo and the final checks."""
    fields = {name: getattr(memo, name) or "" for name in MEMO_FIELDS}
    removed = list(memo.removed_citations)
    for _ in range(4):
        checks: list[CitationCheck] = []
        changed = False
        for name in MEMO_FIELDS:
            field_checks = firewall.verify_text(fields[name])
            clean, gone = firewall.filter_text(fields[name], field_checks)
            if gone:
                changed = True
                fields[name] = clean
                field_checks = firewall.verify_text(clean)
            checks += field_checks
            removed += [f"{g}: removed from the memo by the Citation Firewall" for g in gone]
        if not changed:
            break

    body = " ".join(fields.values())
    status_by_cite = {c.citation.cite: c.status for c in checks}
    citations = [
        c.model_copy(update={"status": status_by_cite.get(c.citation, c.status)})
        for c in memo.citations if c.marker in body
    ]
    warnings = list(memo.warnings)
    for c in checks:
        if c.status == "warning":
            line = f"{c.citation.case_name or c.citation.cite}, {c.citation.cite}: {c.reason}"
            if not any(c.citation.cite in w for w in warnings):
                warnings.append(line)
    cleaned = memo.model_copy(update=fields | {
        "citations": citations, "removed_citations": list(dict.fromkeys(removed)), "warnings": warnings,
    })
    return cleaned, checks


def export_violations(memo: Memo, firewall) -> list[str]:
    """Everything that would make an export unsafe. Empty list = exportable."""
    problems: list[str] = []
    for name in MEMO_FIELDS:
        for c in firewall.verify_text(getattr(memo, name) or ""):
            if not c.exportable:
                problems.append(f"{c.citation.raw or c.citation.cite} ({c.status}: {c.reason})")
    problems += [f"{c.marker} {c.citation} ({c.status})" for c in memo.citations if c.status not in ("verified", "warning")]
    return problems


class MemoFirewallAgent(BaseAgent):
    name = "citation_firewall"

    def running_summary(self, state: ResearchState) -> str:
        return "Re-checking every citation in the drafted memo"

    def execute(self, state: ResearchState) -> AgentResult:
        memo = load_memo(state)
        cleaned, checks = check_memo(memo, self.deps.firewall)
        prior = [c for c in state.get("checks") or [] if c.get("phase") != "memo"]
        newly_removed = len(cleaned.removed_citations) - len(memo.removed_citations)
        summary = f"Memo: {summarize_checks(checks)}"
        if newly_removed:
            summary += f"; {newly_removed} citation(s) removed from the draft"
        return AgentResult(
            update={
                "memo": dump(cleaned),
                "checks": prior + [{"phase": "memo", **dump(c)} for c in checks],
                "status": "awaiting_memo_approval",
            },
            summary=summary,
            data={"phase": "memo", "removed": newly_removed}
            | {s: sum(c.status == s for c in checks) for s in ("verified", "warning", "blocked", "unresolved")},
        )
