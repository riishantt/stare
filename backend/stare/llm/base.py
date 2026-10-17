"""Chat-model abstraction used by every agent.

Agents call `llm.complete(...)` / `llm.complete_json(...)` when `llm.is_offline` is False, and fall
back to their deterministic rule-based path when it is True. The offline provider is the default so
that the whole system runs without network access or API cost.
"""

from __future__ import annotations

import hashlib
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel

Tier = Literal["main", "fast"]
T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class UnredactedTextError(LLMError):
    """Raised when a prompt still contains personal data patterns (NFR-03 safety net)."""


# Last line of defence: the Intake redactor removes PII before anything reaches an agent; this guard
# refuses to send a prompt that still contains obvious identifiers.
_PII_GUARDS = {
    "US_SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "EMAIL_ADDRESS": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "PHONE_NUMBER": re.compile(r"(?<!\d)(?:\+1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)"),
}


def assert_redacted(text: str) -> None:
    for kind, pattern in _PII_GUARDS.items():
        if pattern.search(text):
            raise UnredactedTextError(f"prompt contains an unredacted {kind}; refusing to call the LLM")


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    by_model: dict[str, int] = field(default_factory=dict)

    def add(self, model: str, input_tokens: int, output_tokens: int, cost: float) -> None:
        self.calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cost_usd += cost
        self.by_model[model] = self.by_model.get(model, 0) + 1


class ChatModel(ABC):
    provider: str = "base"
    is_offline: bool = False

    def __init__(self, main_model: str = "", fast_model: str = "", cache_dir: Path | None = None):
        self.main_model = main_model
        self.fast_model = fast_model or main_model
        self.cache_dir = cache_dir
        self.usage = Usage()

    @property
    def name(self) -> str:
        return f"{self.provider}:{self.main_model}" if self.main_model else self.provider

    def model_for(self, tier: Tier) -> str:
        return self.fast_model if tier == "fast" else self.main_model

    # -- public API --------------------------------------------------------------------------

    def complete(self, system: str, prompt: str, *, tier: Tier = "main", max_tokens: int = 8000) -> str:
        assert_redacted(prompt)
        key = self._cache_key("text", system, prompt, tier, None)
        if (hit := self._cache_get(key)) is not None:
            return hit
        out = self._complete(system, prompt, tier=tier, max_tokens=max_tokens)
        self._cache_put(key, out)
        return out

    def complete_json(
        self, system: str, prompt: str, schema: type[T], *, tier: Tier = "main", max_tokens: int = 8000
    ) -> T:
        assert_redacted(prompt)
        key = self._cache_key("json", system, prompt, tier, schema.__name__)
        if (hit := self._cache_get(key)) is not None:
            return schema.model_validate_json(hit)
        out = self._complete_json(system, prompt, schema, tier=tier, max_tokens=max_tokens)
        self._cache_put(key, out.model_dump_json())
        return out

    # -- provider hooks ----------------------------------------------------------------------

    @abstractmethod
    def _complete(self, system: str, prompt: str, *, tier: Tier, max_tokens: int) -> str: ...

    @abstractmethod
    def _complete_json(self, system: str, prompt: str, schema: type[T], *, tier: Tier, max_tokens: int) -> T: ...

    # -- disk cache (Section 3.9.2: caching controls cost) ------------------------------------

    def _cache_key(self, kind: str, system: str, prompt: str, tier: str, schema: str | None) -> str:
        raw = json.dumps([self.provider, self.model_for(tier), kind, system, prompt, schema])  # type: ignore[arg-type]
        return hashlib.sha256(raw.encode()).hexdigest()

    def _cache_get(self, key: str) -> str | None:
        if not self.cache_dir:
            return None
        p = self.cache_dir / f"{key}.json"
        return p.read_text() if p.exists() else None

    def _cache_put(self, key: str, value: str) -> None:
        if not self.cache_dir:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / f"{key}.json").write_text(value)
