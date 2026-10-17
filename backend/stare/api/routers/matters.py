from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from stare.api.auth import CurrentUser, get_current_user, require_roles
from stare.api.deps import get_db
from stare.api.schemas_api import DocumentOut, EntityOut, MatterCreate, MatterDetail, MatterSummary, RunBrief
from stare.courts.hierarchy import CourtHierarchy
from stare.db.models import CaseFile, CourtRow, Document, ResearchRun
from stare.graph.service import audit

router = APIRouter(prefix="/matters", tags=["matters"])


def document_out(d: Document) -> DocumentOut:
    ents = d.redaction_entities or []
    return DocumentOut(
        id=d.id, file_name=d.file_name, page_count=d.page_count, ocr_used=d.ocr_used,
        redacted_text=d.redacted_text, redaction_count=len(ents),
        entities=[EntityOut(entity_type=e.get("entity_type", ""), placeholder=e.get("placeholder", ""),
                            start=e.get("start"), end=e.get("end")) for e in ents],
        redaction_engine=d.redaction_engine, created_at=d.created_at,
    )


def _court_names(db: Session, ids: set[str]) -> dict[str, str]:
    names = {r.id: r.name for r in db.scalars(select(CourtRow).where(CourtRow.id.in_(ids)))} if ids else {}
    h = CourtHierarchy.default()
    for cid in ids - names.keys():
        c = h.get(cid)
        names[cid] = c.name if c else cid
    return names


def _summaries(db: Session, cases: list[CaseFile]) -> list[MatterSummary]:
    if not cases:
        return []
    ids = [c.id for c in cases]
    doc_counts = dict(db.execute(select(Document.case_id, func.count(Document.id))
                                 .where(Document.case_id.in_(ids)).group_by(Document.case_id)).all())
    last: dict[int, str] = {}
    for cid, status in db.execute(select(ResearchRun.case_id, ResearchRun.status)
                                  .where(ResearchRun.case_id.in_(ids)).order_by(ResearchRun.id)):
        last[cid] = status
    names = _court_names(db, {c.court_id for c in cases if c.court_id})
    return [MatterSummary(
        id=c.id, matter_number=c.matter_number, title=c.title, court_id=c.court_id,
        court_name=names.get(c.court_id) if c.court_id else None, claims=c.claims or [], status=c.status,
        created_at=c.created_at, last_run_status=last.get(c.id), document_count=doc_counts.get(c.id, 0),
    ) for c in cases]


def ensure_court(db: Session, court_id: str) -> None:
    """The matter FK needs a courts row; seed it from the built-in hierarchy on first use."""
    if db.get(CourtRow, court_id):
        return
    c = CourtHierarchy.default().get(court_id)
    if c is None:
        raise HTTPException(status_code=422, detail=f"Unknown court '{court_id}'")
    db.add(CourtRow(id=c.id, name=c.name, short_name=c.short_name, level=c.level, circuit=c.circuit, state=c.state))
    db.flush()


def _next_matter_number(db: Session) -> str:
    n = 0
    for (mn,) in db.execute(select(CaseFile.matter_number)):
        m = re.fullmatch(r"M-(\d+)", mn or "")
        if m:
            n = max(n, int(m.group(1)))
    return f"M-{n + 1:04d}"


@router.get("", response_model=list[MatterSummary])
def list_matters(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    cases = list(db.scalars(select(CaseFile).order_by(CaseFile.id.desc())))
    return _summaries(db, cases)


@router.post("", response_model=MatterSummary, status_code=201)
def create_matter(body: MatterCreate, user: CurrentUser = Depends(require_roles("attorney", "paralegal")),
                  db: Session = Depends(get_db)):
    if body.court_id:
        ensure_court(db, body.court_id)
    for attempt in range(3):  # matter_number is unique; retry if two requests raced
        case = CaseFile(matter_number=_next_matter_number(db), title=body.title, user_id=user.id,
                        court_id=body.court_id, notes=body.notes)
        db.add(case)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
            if body.court_id:
                ensure_court(db, body.court_id)
            if attempt == 2:
                raise
    audit(db, user.id, "matter.created", "matter", case.id, matter_number=case.matter_number)
    db.commit()
    return _summaries(db, [case])[0]


@router.get("/{matter_id}", response_model=MatterDetail)
def get_matter(matter_id: int, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    case = db.get(CaseFile, matter_id)
    if case is None:
        raise LookupError(f"matter {matter_id} not found")
    base = _summaries(db, [case])[0]
    docs = list(db.scalars(select(Document).where(Document.case_id == matter_id).order_by(Document.id)))
    runs = list(db.scalars(select(ResearchRun).where(ResearchRun.case_id == matter_id).order_by(ResearchRun.id.desc())))
    return MatterDetail(**base.model_dump(), notes=case.notes, case_record=case.case_record,
                        documents=[document_out(d) for d in docs],
                        runs=[RunBrief(id=r.id, status=r.status, created_at=r.created_at, llm_provider=r.llm_provider)
                              for r in runs])
