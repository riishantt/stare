from __future__ import annotations

from functools import cache

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from stare.api.auth import CurrentUser, create_token, get_current_user, hash_password, verify_password
from stare.api.deps import get_db, get_settings_dep
from stare.api.schemas_api import LoginIn, TokenOut, UserOut
from stare.config import Settings
from stare.db.models import User
from stare.graph.service import audit

router = APIRouter(prefix="/auth", tags=["auth"])



@cache
def _dummy_hash() -> str:
    # verified against when the e-mail is unknown so response time does not reveal which accounts exist
    return hash_password("not-a-real-password")


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    ok = verify_password(body.password, user.password_hash if user else _dummy_hash())
    if not (user and ok and user.active):
        reason = "unknown_user" if user is None else "inactive" if not user.active and ok else "bad_password"
        audit(db, user.id if user else None, "auth.login_failed", "user", user.id if user else None,
              email=email, reason=reason)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid e-mail or password")
    audit(db, user.id, "auth.login", "user", user.id, role=user.role)
    db.commit()
    return TokenOut(access_token=create_token(user, settings), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(cu: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.get(User, cu.id)
