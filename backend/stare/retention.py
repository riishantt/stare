"""Data retention: purge matters whose last activity is older than the administrator's retention period.

A matter is purged with its documents, research runs, agent steps, citation checks, memos and LangGraph
checkpoints. The audit log is kept: it holds no client text and is the firm's record of what was done.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stare.db.models import AuditLog, CaseFile, ResearchRun, Setting

DEFAULT_RETENTION_DAYS = 365


def retention_days(session: Session) -> int:
    row = session.get(Setting, "retention_days")
    return int(row.value.get("value", DEFAULT_RETENTION_DAYS)) if row else DEFAULT_RETENTION_DAYS


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def purge_expired(session: Session, days: int | None = None, *, now: datetime | None = None,
                  checkpointer=None, user_id: int | None = None) -> dict:
    """Delete expired matters. Returns {"matters": n, "runs": n, "cutoff": iso}."""
    days = days or retention_days(session)
    cutoff = (now or datetime.now(UTC)) - timedelta(days=days)
    last_run = dict(session.execute(
        select(ResearchRun.case_id, func.max(ResearchRun.created_at)).group_by(ResearchRun.case_id)
    ).all())
    expired = [
        c for c in session.scalars(select(CaseFile))
        if max(_aware(c.created_at), _aware(last_run.get(c.id) or c.created_at)) < cutoff
    ]
    runs = 0
    for case in expired:
        for run in case.runs:
            runs += 1
            if checkpointer is not None:
                try:
                    checkpointer.delete_thread(run.thread_id)
                except Exception:  # a missing checkpoint must not stop the purge
                    pass
        session.delete(case)  # cascades to documents, runs, steps, checks and memos
    if expired:
        session.add(AuditLog(user_id=user_id, action="retention.purged", entity="matter", entity_id=None,
                             detail={"matters": len(expired), "runs": runs, "retention_days": days,
                                     "matter_numbers": [c.matter_number for c in expired]}))
    session.commit()
    return {"matters": len(expired), "runs": runs, "cutoff": cutoff.isoformat(timespec="seconds")}
