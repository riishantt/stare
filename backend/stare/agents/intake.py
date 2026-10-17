"""Intake Agent: redacted complaint text -> structured case record + draft research plan (FR-03, FR-04).

Text extraction, OCR and redaction happen at upload time (the document route), so that the paralegal
can review the redacted text before any agent runs. This agent only ever sees redacted text.
"""

from __future__ import annotations

from stare.agents.base import AgentResult, BaseAgent
from stare.agents.state import ResearchState, dump
from stare.intake.extractor import extract_case_record
from stare.intake.planner import draft_plan
from stare.schemas import CaseRecord


class IntakeAgent(BaseAgent):
    name = "intake"

    def running_summary(self, state: ResearchState) -> str:
        return f"Reading {len(state.get('document_ids') or [])} document(s)"

    def execute(self, state: ResearchState) -> AgentResult:
        text = state.get("redacted_text") or ""
        if state.get("case_record"):
            # The matter already has an attorney-reviewed record; keep it and only fill gaps.
            record = CaseRecord.model_validate(state["case_record"])
            if not record.claims and text:
                record = extract_case_record(text, self.llm, self.deps.hierarchy)
        else:
            record = extract_case_record(text, self.llm, self.deps.hierarchy)
        plan = draft_plan(record, self.llm)
        parties = len(record.parties)
        summary = (
            f"Read {len(state.get('document_ids') or [])} document(s); {parties} parties, "
            f"{len(record.claims)} claims, {len(record.key_dates)} dates; {record.redaction_count} personal details redacted"
        )
        return AgentResult(
            update={"case_record": dump(record), "plan": dump(plan), "status": "awaiting_plan_approval"},
            summary=summary,
            data={"claims": [c.model_dump() for c in record.claims], "court_id": record.court_id,
                  "plan_items": len(plan.items)},
        )
