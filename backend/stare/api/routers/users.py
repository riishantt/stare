from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from stare.api.auth import CurrentUser, hash_password, require_roles
from stare.api.deps import get_db
from stare.api.schemas_api import UserCreate, UserOut, UserPatch
from stare.db.models import User
from stare.graph.service import audit

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(admin: CurrentUser = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    return list(db.scalars(select(User).order_by(User.id)))


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, admin: CurrentUser = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="A user with this e-mail already exists")
    user = User(name=body.name, email=email, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.flush()
    audit(db, admin.id, "user.created", "user", user.id, role=user.role, email=email)
    db.commit()
    return user


@router.patch("/{user_id}", response_model=UserOut)
def patch_user(user_id: int, body: UserPatch, admin: CurrentUser = Depends(require_roles("admin")),
               db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise LookupError(f"user {user_id} not found")
    if user.id == admin.id and (body.active is False or (body.role and body.role != "admin")):
        raise HTTPException(status_code=409, detail="Administrators cannot deactivate or demote themselves")
    changed: list[str] = []
    if body.name is not None:
        user.name = body.name
        changed.append("name")
    if body.role is not None and body.role != user.role:
        user.role = body.role
        changed.append("role")
    if body.active is not None and body.active != user.active:
        user.active = body.active
        changed.append("active")
    if body.password is not None:
        user.password_hash = hash_password(body.password)
        changed.append("password")
    audit(db, admin.id, "user.updated", "user", user.id, changed=changed, role=user.role, active=user.active)
    db.commit()
    return user
