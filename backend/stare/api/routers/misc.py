"""Health, courts, standalone Citation Firewall check and opinion viewer."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stare import __version__
from stare.api.auth import CurrentUser, get_current_user
from stare.api.deps import get_db, get_service, get_settings_dep
from stare.api.schemas_api import FirewallCheckIn, FirewallCheckOut, HealthOut, OpinionOut
from stare.citations.firewall import FirewallReport
from stare.config import Settings
from stare.courts.hierarchy import CourtHierarchy
from stare.db.models import Chunk, CourtRow, Opinion, StatuteSection
from stare.graph.service import ResearchService, audit
from stare.schemas import Court

router = APIRouter()


def get_redactor():
    """One shared redactor (Presidio models are expensive to load). Tests monkeypatch this."""
    global _redactor
    if _redactor is None:
        from stare.intake.redactor import PIIRedactor

        _redactor = PIIRedactor()
    return _redactor


_redactor = None


@router.get("/health", response_model=HealthOut, tags=["system"])
def health(db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    from stare.retrieval.hybrid import META_FILE

    try:
        corpus = {
            "opinions": db.scalar(select(func.count(Opinion.id))) or 0,
            "statutes": db.scalar(select(func.count(StatuteSection.id))) or 0,
            "chunks": db.scalar(select(func.count(Chunk.id))) or 0,
        }
        status = "ok"
    except Exception:
        corpus, status = {"opinions": 0, "statutes": 0, "chunks": 0}, "degraded"
    return HealthOut(status=status, version=__version__, llm_provider=settings.llm_provider, corpus=corpus,
                     index_built=(settings.index_dir / META_FILE).exists())


@router.get("/courts", response_model=list[Court], tags=["courts"])
def courts(user: CurrentUser = Depends(get_current_user)):
    return CourtHierarchy.default().all()


@router.post("/firewall/check", response_model=FirewallCheckOut, tags=["firewall"])
def firewall_check(body: FirewallCheckIn, user: CurrentUser = Depends(get_current_user),
                   db: Session = Depends(get_db), service: ResearchService = Depends(get_service)):
    redaction = get_redactor().redact(body.text)  # nothing un-redacted is stored or returned
    fw = service.deps.firewall
    checks = fw.verify_text(redaction.text)
    cleaned, removed = fw.filter_text(redaction.text, checks)
    report = FirewallReport.from_checks(checks)
    audit(db, user.id, "firewall.checked", "firewall", None, chars=len(body.text), redactions=len(redaction.entities),
          citations=report.total, **report.counts, removed=len(removed))
    db.commit()
    return FirewallCheckOut(checks=checks, summary=report.summary(), counts=report.counts,
                            exportable=report.exportable, cleaned_text=cleaned, removed=list(removed),
                            redaction_count=len(redaction.entities))


def opinion_url(op: Opinion) -> str | None:
    if op.url:
        return op.url
    if op.source.startswith("courtlistener") and op.source_id:
        return f"https://www.courtlistener.com/opinion/{op.source_id}/"
    return None


@router.get("/opinions/{opinion_id}", response_model=OpinionOut, tags=["opinions"])
def get_opinion(opinion_id: int, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    op = db.get(Opinion, opinion_id)
    if op is None:
        raise LookupError(f"opinion {opinion_id} not found")
    court = db.get(CourtRow, op.court_id) if op.court_id else None
    if court is None and op.court_id:
        c = CourtHierarchy.default().get(op.court_id)
        court_name = c.name if c else op.court_id
    else:
        court_name = court.name if court else None
    return OpinionOut(id=op.id, case_name=op.case_name, citation=op.citation, court=court_name, court_id=op.court_id,
                      date_filed=op.date_filed, url=opinion_url(op), text=op.plain_text)
