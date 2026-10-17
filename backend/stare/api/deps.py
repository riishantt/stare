"""Shared FastAPI dependencies: lazily-built application state (session factory, settings, service)."""

from __future__ import annotations

import threading
from collections.abc import Iterator

from fastapi import FastAPI, Request
from sqlalchemy.orm import Session, sessionmaker

from stare.config import Settings
from stare.graph.service import ResearchService

_lock = threading.Lock()


def ensure_state(app: FastAPI) -> None:
    """Resolve settings and the session factory and create tables, once. No graph is built here."""
    st = app.state
    if getattr(st, "ready", False):
        return
    with _lock:
        if getattr(st, "ready", False):
            return
        from stare.config import get_settings
        from stare.db.models import Base
        from stare.db.session import get_sessionmaker

        service = st.service
        sf = st.session_factory or (service.sf if service else get_sessionmaker())
        st.session_factory = sf
        st.settings = service.settings if service else get_settings()
        Base.metadata.create_all(sf.kw["bind"])
        from stare.retention import purge_expired

        with sf() as session:
            purge_expired(session)  # enforce the administrator's retention period on start-up
        st.ready = True


def get_sf(request: Request) -> sessionmaker[Session]:
    ensure_state(request.app)
    return request.app.state.session_factory


def get_settings_dep(request: Request) -> Settings:
    ensure_state(request.app)
    return request.app.state.settings


def get_db(request: Request) -> Iterator[Session]:
    with get_sf(request)() as session:
        yield session


def get_service(request: Request) -> ResearchService:
    app = request.app
    ensure_state(app)
    with _lock:
        if app.state.service is None:
            app.state.service = ResearchService(app.state.session_factory, app.state.settings)
    return app.state.service
