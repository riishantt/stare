from __future__ import annotations

import asyncio
import io
import json
import re

from fastapi import APIRouter, Body, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from stare.api.auth import CurrentUser, get_current_user, get_current_user_sse, require_roles
from stare.api.deps import get_db, get_service
from stare.api.routers import misc
from stare.api.schemas_api import GraphEdge, GraphNode, GraphOut, MemoChangesIn, RunOut
from stare.db.models import CaseFile, CitationEdge
from stare.graph.service import ResearchService
from stare.schemas import CaseRecord, Memo, ResearchPlan

router = APIRouter(tags=["runs"])
TERMINAL = {"exported", "cancelled", "failed"}
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_WRITERS = ("attorney", "paralegal")


@router.post("/matters/{matter_id}/runs", response_model=RunOut, status_code=201)
def start_run(matter_id: int, user: CurrentUser = Depends(require_roles(*_WRITERS)),
              service: ResearchService = Depends(get_service)):
    run_id = service.start_run(matter_id, user.id)
    return service.snapshot(run_id)


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: int, user: CurrentUser = Depends(get_current_user), service: ResearchService = Depends(get_service)):
    return service.snapshot(run_id)


@router.put("/runs/{run_id}/case-record", response_model=RunOut)
def put_case_record(run_id: int, record: CaseRecord, user: CurrentUser = Depends(require_roles(*_WRITERS)),
                    service: ResearchService = Depends(get_service)):
    before = CaseRecord.model_validate(service.snapshot(run_id)["case_record"] or {})
    service.update_case_record(run_id, redact_case_record(record, before, misc.get_redactor()), user.id)
    return service.snapshot(run_id)


def redact_case_record(record: CaseRecord, before: CaseRecord, redactor) -> CaseRecord:
    """Hand-typed text may reintroduce identifiers (NFR-03), so it passes through the redactor like an edited
    document. Party names already in the stored record (placeholders, company defendants) are kept as they are."""
    count = 0

    def red(text: str) -> str:
        nonlocal count
        if not text:
            return text
        r = redactor.redact(text)
        count += len(r.entities)
        return r.text

    known = {p.name for p in before.parties}
    return record.model_copy(update={
        "facts_summary": red(record.facts_summary),
        "procedural_posture": red(record.procedural_posture),
        "parties": [p if p.name in known else p.model_copy(update={"name": red(p.name)}) for p in record.parties],
        "claims": [c.model_copy(update={"description": red(c.description)}) for c in record.claims],
        "key_dates": [k.model_copy(update={"label": red(k.label)}) for k in record.key_dates],
        "redaction_count": before.redaction_count + count,
    })


@router.post("/runs/{run_id}/plan/approve", response_model=RunOut)
def approve_plan(run_id: int, plan: ResearchPlan, user: CurrentUser = Depends(require_roles("attorney")),
                 service: ResearchService = Depends(get_service)):
    drafted = service.snapshot(run_id)["plan"]
    before = ResearchPlan.model_validate(drafted) if drafted else None
    service.approve_plan(run_id, redact_plan(plan, before, misc.get_redactor()), user.id)
    return service.snapshot(run_id)


def redact_plan(plan: ResearchPlan, before: ResearchPlan | None, redactor) -> ResearchPlan:
    """The approved plan goes into the research and memo prompts, so text the attorney typed into it
    (instruction, elements, issues) passes through the redactor like an edited case record (NFR-03).
    Text unchanged from the drafted plan, which came from the redacted case record, is kept as it is."""
    drafted: set[str] = set()
    if before is not None:
        drafted = {before.question, before.instructions}
        for i in before.items:
            drafted |= {i.issue, *i.elements, *i.queries}

    def red(text: str) -> str:
        return text if not text or text in drafted else redactor.redact(text).text

    return plan.model_copy(update={
        "question": red(plan.question),
        "instructions": red(plan.instructions),
        "items": [i.model_copy(update={"issue": red(i.issue), "elements": [red(e) for e in i.elements],
                                       "queries": [red(q) for q in i.queries]}) for i in plan.items],
    })


@router.post("/runs/{run_id}/memo/changes", response_model=RunOut)
def memo_changes(run_id: int, body: MemoChangesIn, user: CurrentUser = Depends(require_roles("attorney")),
                 service: ResearchService = Depends(get_service)):
    # the instruction is stored with the memo and shown to the Memo Agent, so it is redacted first
    service.request_memo_changes(run_id, misc.get_redactor().redact(body.instruction).text, user.id)
    return service.snapshot(run_id)


@router.post("/runs/{run_id}/memo/approve", response_model=RunOut)
def approve_memo(run_id: int, memo: Memo | None = Body(default=None),
                 user: CurrentUser = Depends(require_roles("attorney")),
                 service: ResearchService = Depends(get_service)):
    service.approve_memo(run_id, memo, user.id)
    return service.snapshot(run_id)


@router.post("/runs/{run_id}/cancel", response_model=RunOut)
def cancel_run(run_id: int, user: CurrentUser = Depends(require_roles("attorney")),
               service: ResearchService = Depends(get_service)):
    service.cancel(run_id, user.id)
    return service.snapshot(run_id)


@router.get("/runs/{run_id}/export.docx")
def export_docx(run_id: int, user: CurrentUser = Depends(require_roles("attorney")),
                service: ResearchService = Depends(get_service), db: Session = Depends(get_db)):
    data = service.export_docx(run_id, user.id)  # raises 409 unless approved and the export check passes
    case = db.get(CaseFile, service.snapshot(run_id)["case_id"])
    matter = re.sub(r"[^A-Za-z0-9_.-]", "_", case.matter_number if case else "matter")
    return StreamingResponse(
        io.BytesIO(data), media_type=DOCX_TYPE,
        headers={"Content-Disposition": f'attachment; filename="STARE-memo-{matter}-run{run_id}.docx"',
                 "Content-Length": str(len(data))},
    )


# ------------------------------------------------------------------------------------------------ SSE
def _sse(event: str, payload: dict) -> dict:
    return {"event": event, "data": json.dumps(jsonable_encoder(payload))}


@router.get("/runs/{run_id}/events")
async def run_events(run_id: int, request: Request, user: CurrentUser = Depends(get_current_user_sse),
                     service: ResearchService = Depends(get_service)):
    # subscribe before reading the persisted steps so no event can fall between replay and live stream
    sub = service.subscribe(run_id)
    try:
        snap = await asyncio.to_thread(service.snapshot, run_id)
    except LookupError:
        sub.close()
        raise

    async def stream():
        try:
            last_seq = 0
            for st in snap["steps"]:
                last_seq = max(last_seq, st["seq"])
                yield _sse("trace", {"run_id": run_id, "agent": st["agent"], "status": st["status"],
                                     "summary": st["summary"], "started_at": st["started_at"],
                                     "ended_at": st["ended_at"], "duration_ms": st["duration_ms"],
                                     "data": st["data"], "seq": st["seq"]})
            yield _sse("status", {"run_id": run_id, "status": snap["status"], "error": snap["error"]})
            if snap["status"] in TERMINAL:
                return
            while True:
                ev = await asyncio.to_thread(sub.get, 1.0)
                if ev is None:
                    if await request.is_disconnected():
                        return
                    continue
                kind = ev.get("type", "trace")
                body = {k: v for k, v in ev.items() if k != "type"}
                if kind == "trace":
                    if body.get("seq", 0) <= last_seq:
                        continue  # already replayed
                    last_seq = body["seq"]
                yield _sse(kind, body)
                if kind == "status" and body.get("status") in TERMINAL:
                    return
        finally:
            sub.close()

    return EventSourceResponse(stream(), ping=15)


# ------------------------------------------------------------------------------------------------ graph
@router.get("/runs/{run_id}/graph", response_model=GraphOut)
def run_graph(run_id: int, user: CurrentUser = Depends(get_current_user),
              service: ResearchService = Depends(get_service), db: Session = Depends(get_db)):
    snap = service.snapshot(run_id)
    nodes: dict[str, GraphNode] = {}
    opinion_of: dict[int, str] = {}
    for adverse, items in ((False, snap["authorities"]), (True, snap["adverse"])):
        for a in items:
            key = a.get("key") or f"op:{a.get('opinion_id')}"
            if key in nodes:
                nodes[key].adverse = nodes[key].adverse or adverse or bool(a.get("adverse"))
                continue
            ver = a.get("verification") or {}
            nodes[key] = GraphNode(
                id=key, label=a.get("case_name") or a.get("citation", key), citation=a.get("citation", ""),
                status=(a.get("rank") or {}).get("status"), check_status=ver.get("status"),
                court=a.get("court_name") or a.get("court_id"), year=a.get("year"),
                adverse=adverse or bool(a.get("adverse")),
            )
            if a.get("opinion_id") is not None:
                opinion_of[a["opinion_id"]] = key
    edges: list[GraphEdge] = []
    if len(opinion_of) > 1:
        ids = list(opinion_of)
        for e in db.scalars(select(CitationEdge).where(CitationEdge.citing_id.in_(ids), CitationEdge.cited_id.in_(ids))):
            edges.append(GraphEdge(source=opinion_of[e.citing_id], target=opinion_of[e.cited_id], treatment=e.treatment))
    return GraphOut(nodes=list(nodes.values()), edges=edges)
