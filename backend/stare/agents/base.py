"""BaseAgent and the dependencies every agent receives (Figure 8, class diagram)."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import cached_property
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from stare.agents.state import ResearchState
from stare.config import Settings, get_settings
from stare.courts.hierarchy import AuthorityRanker, CourtHierarchy
from stare.llm.base import ChatModel
from stare.schemas import AgentName, TraceEvent

Emit = Callable[[TraceEvent], None]


@dataclass
class AgentDeps:
    llm: ChatModel
    session_factory: sessionmaker[Session]
    settings: Settings = field(default_factory=get_settings)
    emit: Emit = lambda event: None  # noqa: E731
    hierarchy: CourtHierarchy = field(default_factory=CourtHierarchy.default)

    @cached_property
    def ranker(self) -> AuthorityRanker:
        return AuthorityRanker(self.hierarchy)

    @cached_property
    def retriever(self):
        from stare.retrieval.hybrid import HybridRetriever

        return HybridRetriever(self.session_factory, self.settings)

    @cached_property
    def firewall(self):
        from stare.citations.firewall import CitationFirewall

        return CitationFirewall(self.session_factory, self.settings)


@dataclass
class AgentResult:
    update: dict[str, Any]
    summary: str
    data: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    name: AgentName

    def __init__(self, deps: AgentDeps):
        self.deps = deps

    @property
    def llm(self) -> ChatModel:
        return self.deps.llm

    def run(self, state: ResearchState) -> dict[str, Any]:
        """Run the agent, emitting running/done trace events with timing (FR-11)."""
        run_id = state.get("run_id", 0)
        started = datetime.now(UTC)
        t0 = time.perf_counter()
        self.deps.emit(TraceEvent(run_id=run_id, agent=self.name, status="running", started_at=started,
                                  summary=self.running_summary(state)))
        try:
            result = self.execute(state)
        except Exception as exc:
            ms = int((time.perf_counter() - t0) * 1000)
            self.deps.emit(TraceEvent(run_id=run_id, agent=self.name, status="error", started_at=started,
                                      ended_at=datetime.now(UTC), duration_ms=ms, summary=f"{type(exc).__name__}: {exc}"))
            raise
        ms = int((time.perf_counter() - t0) * 1000)
        self.deps.emit(TraceEvent(run_id=run_id, agent=self.name, status="done", started_at=started,
                                  ended_at=datetime.now(UTC), duration_ms=ms, summary=result.summary, data=result.data))
        timings = dict(state.get("timings") or {})
        timings[self.name] = timings.get(self.name, 0) + ms
        return {**result.update, "timings": timings}

    def running_summary(self, state: ResearchState) -> str:
        return "working"

    @abstractmethod
    def execute(self, state: ResearchState) -> AgentResult: ...
