from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from stare.api.auth import CurrentUser, require_roles
from stare.api.deps import get_db, get_settings_dep
from stare.api.schemas_api import AuditOut, SettingsOut, SettingsPatch
from stare.config import Settings
from stare.db.models import AuditLog, Setting, User
from stare.graph.service import audit
from stare.retention import purge_expired

router = APIRouter(tags=["admin"])

DEFAULT_RETENTION_DAYS = 365


def _settings_out(db: Session, settings: Settings) -> SettingsOut:
    row = db.get(Setting, "retention_days")
    days = int(row.value.get("value", DEFAULT_RETENTION_DAYS)) if row else DEFAULT_RETENTION_DAYS
    return SettingsOut(retention_days=days, llm_provider=settings.llm_provider, model=settings.llm_model,
                       fast_model=settings.llm_fast_model)


@router.get("/audit", response_model=list[AuditOut])
def list_audit(
    run_id: int | None = None, user_id: int | None = None, action: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    admin: CurrentUser = Depends(require_roles("admin")), db: Session = Depends(get_db),
):
    q = select(AuditLog, User.name).outerjoin(User, User.id == AuditLog.user_id)
    if run_id is not None:
        q = q.where(AuditLog.entity == "run", AuditLog.entity_id == run_id)
    if user_id is not None:
        q = q.where(AuditLog.user_id == user_id)
    if action:
        q = q.where(AuditLog.action == action)
    rows = db.execute(q.order_by(AuditLog.id.desc()).limit(limit)).all()
    return [AuditOut(id=r.id, at=r.at, user_id=r.user_id, user_name=name, action=r.action, entity=r.entity,
                     entity_id=r.entity_id, detail=r.detail or {}) for r, name in rows]


@router.get("/settings", response_model=SettingsOut)
def get_settings_route(admin: CurrentUser = Depends(require_roles("admin")), db: Session = Depends(get_db),
                       settings: Settings = Depends(get_settings_dep)):
    return _settings_out(db, settings)


@router.patch("/settings", response_model=SettingsOut)
def patch_settings(body: SettingsPatch, admin: CurrentUser = Depends(require_roles("admin")),
                   db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    if body.retention_days is not None:
        row = db.get(Setting, "retention_days")
        if row is None:
            db.add(Setting(key="retention_days", value={"value": body.retention_days}))
        else:
            row.value = {"value": body.retention_days}
        audit(db, admin.id, "settings.updated", "setting", None, retention_days=body.retention_days)
        db.commit()
        purge_expired(db, body.retention_days, user_id=admin.id)
    return _settings_out(db, settings)
