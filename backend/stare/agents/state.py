"""ResearchState: the single object every agent reads and updates (Section 5.3.1).

LangGraph checkpoints this state after every node, so all values are plain JSON (Pydantic models are
stored with `.model_dump(mode="json")` and re-validated with the helpers below).
"""

from __future__ import annotations

from typing import Any, TypedDict

from stare.schemas import Authority, CaseRecord, CitationCheck, Memo, ResearchPlan


class ResearchState(TypedDict, total=False):
    run_id: int
    case_id: int
    user_id: int
    # intake
    document_ids: list[int]
    redacted_text: str  # concatenated redacted text of the matter's documents
    case_record: dict  # CaseRecord
    plan: dict  # ResearchPlan
    plan_approved: bool
    # research
    candidates: list[dict]  # list[Authority] from the Research Agent
    shortlist: list[dict]  # list[Authority] ranked by the Precedent Agent
    adverse: list[dict]  # list[Authority] from the Opposing Counsel Agent
    adverse_report: str  # Opposing Counsel's written report (the Memo Agent may not drop it)
    procedural_flags: list[str]  # deterministic timeliness checks from the key dates
    checks: list[dict]  # list[CitationCheck] from the Citation Firewall
    verified: list[dict]  # list[Authority] that passed the Firewall (status verified or warning)
    rejected: list[dict]  # [{"citation":..., "reason":...}] fed back to the Research Agent (Reflexion-style)
    loop_count: int
    retry_research: bool  # set by the Firewall when too few authorities passed (CRAG-style loop)
    # memo
    memo: dict  # Memo
    memo_feedback: str  # attorney's request for changes
    memo_approved: bool
    approved_by: int
    # bookkeeping
    status: str
    error: str
    timings: dict[str, int]  # agent -> ms
    plan_approved_at_ms: int  # epoch ms; latency is measured from here (NFR-02)


def load_case_record(state: ResearchState) -> CaseRecord:
    return CaseRecord.model_validate(state.get("case_record") or {})


def load_plan(state: ResearchState) -> ResearchPlan:
    return ResearchPlan.model_validate(state["plan"])


def load_authorities(items: list[dict] | None) -> list[Authority]:
    return [Authority.model_validate(a) for a in items or []]


def load_checks(items: list[dict] | None) -> list[CitationCheck]:
    return [CitationCheck.model_validate(c) for c in items or []]


def load_memo(state: ResearchState) -> Memo | None:
    return Memo.model_validate(state["memo"]) if state.get("memo") else None


def dump(obj: Any) -> Any:
    """Pydantic model(s) -> JSON-safe dict(s) for the state."""
    if isinstance(obj, list):
        return [dump(o) for o in obj]
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return obj
