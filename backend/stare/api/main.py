"""FastAPI application factory. `uvicorn stare.api.main:app` builds the app lazily on first access."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, sessionmaker

from stare import __version__
from stare.api.deps import ensure_state
from stare.api.routers import admin, auth_routes, documents, matters, misc, runs, users
from stare.config import get_settings
from stare.graph.service import ExportBlockedError, MemoVerificationError, ResearchService, RunStateError


def _json(status: int, message: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": message, **extra})


def create_app(service: ResearchService | None = None, session_factory: sessionmaker[Session] | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        ensure_state(app)  # init_db
        yield
        svc = app.state.service
        if svc is not None and svc is not service:
            svc.pool.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="STARE API", version=__version__, lifespan=lifespan)
    app.state.service = service
    app.state.session_factory = session_factory
    app.state.ready = False

    origins = (service.settings if service else get_settings()).cors_origins
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(LookupError)
    async def _lookup(_: Request, exc: LookupError):
        return _json(404, str(exc.args[0]) if exc.args else "Not found")

    @app.exception_handler(ExportBlockedError)
    async def _blocked(_: Request, exc: ExportBlockedError):
        return _json(409, str(exc), problems=exc.problems)

    @app.exception_handler(RunStateError)
    async def _state(_: Request, exc: RunStateError):
        return _json(409, str(exc))

    @app.exception_handler(MemoVerificationError)
    async def _memo(_: Request, exc: MemoVerificationError):
        return _json(422, str(exc), problems=exc.problems)

    @app.exception_handler(PermissionError)
    async def _perm(_: Request, exc: PermissionError):
        return _json(403, str(exc) or "Forbidden")

    from stare.retrieval.hybrid import IndexNotBuiltError, IndexStaleError

    @app.exception_handler(IndexNotBuiltError)
    @app.exception_handler(IndexStaleError)
    async def _index(_: Request, exc: Exception):
        return _json(503, f"{exc} The legal corpus index is unavailable; ask an administrator to ingest the corpus "
                          "and run `stare index build`.")

    for module in (auth_routes, users, misc, matters, documents, runs, admin):
        app.include_router(module.router, prefix="/api")
    return app


_app: FastAPI | None = None


def __getattr__(name: str):  # lazy module-level `app` so importing this module has no side effects
    global _app
    if name == "app":
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(name)
