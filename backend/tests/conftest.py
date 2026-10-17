"""Shared test fixtures. Every test runs against a throwaway data directory and SQLite database."""

from __future__ import annotations

import pytest

from stare.config import get_settings
from stare.db import session as db_session


def _reset_caches() -> None:
    get_settings.cache_clear()
    db_session.get_engine.cache_clear()
    db_session.get_sessionmaker.cache_clear()


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("STARE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("STARE_LLM_PROVIDER", "offline")
    monkeypatch.setenv("STARE_COURTLISTENER_ENABLED", "false")  # tests never depend on the network
    monkeypatch.setenv("STARE_CAP_LOOKUP_ENABLED", "false")
    for key in ("STARE_COURTLISTENER_TOKEN", "STARE_LLM_API_KEY"):  # private keys in backend/.env.local stay unused
        monkeypatch.setenv(key, "")
    _reset_caches()
    yield get_settings()
    _reset_caches()


@pytest.fixture
def session_factory(settings):
    db_session.init_db()
    return db_session.get_sessionmaker()


@pytest.fixture
def session(session_factory):
    s = session_factory()
    try:
        yield s
    finally:
        s.close()
