"""In-process event bus for the live agent trace (FR-11).

Agents run in worker threads; the API streams events to browsers over SSE from the asyncio loop. The bus
is therefore thread-safe and delivers to plain `queue.Queue` subscribers, which the SSE endpoint polls.
Every event is also persisted as an AgentStep row by the ResearchService.
"""

from __future__ import annotations

import itertools
import queue
import threading
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class EventSubscription:
    run_id: int
    queue: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=1000))
    _bus: EventBus | None = None

    def get(self, timeout: float = 1.0) -> dict | None:
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self) -> None:
        if self._bus:
            self._bus.unsubscribe(self)


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[int, list[EventSubscription]] = defaultdict(list)
        self._lock = threading.Lock()
        self._seq = itertools.count(1)

    def next_seq(self) -> int:
        return next(self._seq)

    def subscribe(self, run_id: int) -> EventSubscription:
        sub = EventSubscription(run_id=run_id, _bus=self)
        with self._lock:
            self._subs[run_id].append(sub)
        return sub

    def unsubscribe(self, sub: EventSubscription) -> None:
        with self._lock:
            if sub in self._subs.get(sub.run_id, []):
                self._subs[sub.run_id].remove(sub)

    def publish(self, run_id: int, event: dict) -> None:
        with self._lock:
            subs = list(self._subs.get(run_id, []))
        for sub in subs:
            try:
                sub.queue.put_nowait(event)
            except queue.Full:  # a stalled browser must never block the agents
                pass


bus = EventBus()
