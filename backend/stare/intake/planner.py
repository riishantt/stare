"""Draft a research plan from the case record (FR-04). The attorney approves or edits it."""

from __future__ import annotations

from pydantic import BaseModel

from stare.intake.elements import PROCEDURAL, STATUTE_LABEL, theory_for
from stare.llm.base import ChatModel, LLMError
from stare.schemas import CaseRecord, PlanItem, ResearchPlan


def draft_plan(record: CaseRecord, llm: ChatModel | None = None) -> ResearchPlan:
    plan = _template_plan(record)
    if llm is not None and not llm.is_offline:
        try:
            plan = _refine_with_llm(plan, record, llm)
        except LLMError:
            pass  # the template plan is always a valid fallback
    return plan


def _template_plan(record: CaseRecord) -> ResearchPlan:
    items: list[PlanItem] = []
    seen: set[tuple[str, str]] = set()
    statutes: list[str] = []
    for claim in record.claims:
        theory = theory_for(claim.statute, claim.theory)
        if theory is None or (theory.statute, theory.key) in seen:
            continue
        seen.add((theory.statute, theory.key))
        if theory.statute not in statutes:
            statutes.append(theory.statute)
        items.append(PlanItem(
            id=f"P{len(items) + 1}",
            issue=theory.issue,
            statute=theory.statute,
            elements=[e.name for e in theory.elements],
        ))
    for statute in statutes:
        proc = PROCEDURAL[statute]
        items.append(PlanItem(
            id=f"P{len(items) + 1}",
            issue=f"{proc.name} ({STATUTE_LABEL[statute]})",
            statute=statute,  # type: ignore[arg-type]
            elements=[proc.name],
        ))

    court = record.court_name or record.court_id or "the court of filing"
    claims = ", ".join(f"{STATUTE_LABEL[c.statute]} {c.theory.replace('_', ' ')}" for c in record.claims) or "the claims"
    side = "plaintiff" if record.client_side == "plaintiff" else "defendant"
    question = (
        f"What binding and persuasive authority in {court} governs {claims}, "
        f"and how does it apply to the facts for the {side}, including adverse authority that must be addressed?"
    )
    return ResearchPlan(question=question, court_id=record.court_id, items=items, include_adverse=True)


class _PlanDraft(BaseModel):
    question: str
    items: list[PlanItem]


_SYSTEM = (
    "You are a senior US employment-law attorney planning legal research for a federal case. "
    "Refine the research plan: keep issues tied to the claims and court, list the legal elements to research "
    "for each issue, and do not cite any case names or citations (authorities are found later by retrieval)."
)


def _refine_with_llm(plan: ResearchPlan, record: CaseRecord, llm: ChatModel) -> ResearchPlan:
    prompt = (
        f"Case record (personal details redacted):\n{record.model_dump_json(indent=2)}\n\n"
        f"Draft plan:\n{plan.model_dump_json(include={'question', 'items'}, indent=2)}\n\n"
        "Return the refined plan. Keep item ids of the form P1, P2, ..."
    )
    draft = llm.complete_json(_SYSTEM, prompt, _PlanDraft, tier="fast", max_tokens=4000)
    if not draft.items:
        return plan
    return plan.model_copy(update={"question": draft.question or plan.question, "items": draft.items})
