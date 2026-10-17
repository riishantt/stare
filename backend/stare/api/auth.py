"""Password hashing, JWT issuing/validation and role-based dependencies."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from stare.api.deps import get_settings_dep, get_sf
from stare.config import Settings
from stare.db.models import User

ALGORITHM = "HS256"
bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: int
    name: str
    email: str
    role: str


def _pw_bytes(password: str) -> bytes:
    # bcrypt only looks at 72 bytes; pre-hash so long passphrases are not silently truncated
    return hashlib.sha256(password.encode()).hexdigest().encode()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_pw_bytes(password), hashed.encode())
    except ValueError:
        return False


def create_token(user: User, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {"sub": str(user.id), "role": user.role, "iat": now,
               "exp": now + timedelta(minutes=settings.jwt_ttl_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def _unauthorized(msg: str = "Not authenticated") -> HTTPException:
    return HTTPException(status_code=401, detail=msg, headers={"WWW-Authenticate": "Bearer"})


def _resolve(request: Request, token: str | None) -> CurrentUser:
    if not token:
        raise _unauthorized()
    settings = get_settings_dep(request)
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        uid = int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Session expired; sign in again") from None
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _unauthorized("Invalid token") from None
    with get_sf(request)() as s:
        user = s.get(User, uid)
        if user is None or not user.active:
            raise _unauthorized("Account not found or deactivated")
        return CurrentUser(user.id, user.name, user.email, user.role)


def get_current_user(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> CurrentUser:
    return _resolve(request, creds.credentials if creds else None)


def get_current_user_sse(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    token: str | None = Query(default=None),
) -> CurrentUser:
    """EventSource cannot set headers, so the SSE route also accepts ?token=."""
    return _resolve(request, creds.credentials if creds else token)


def require_roles(*roles: str):
    def dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail=f"This action requires the role: {' or '.join(roles)}")
        return user

    return dep


def create_user(session, name: str, email: str, password: str, role: str) -> User:
    """Helper for bootstrap scripts and tests."""
    user = User(name=name, email=email.strip().lower(), password_hash=hash_password(password), role=role)
    session.add(user)
    session.flush()
    return user
