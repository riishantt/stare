"""Chat-model abstraction used by every agent.

Agents call `llm.complete(...)` / `llm.complete_json(...)` when `llm.is_offline` is False, and fall
back to their deterministic rule-based path when it is True. The offline provider is the default so
that the whole system runs without network access or API cost.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel, ValidationError

Tier = Literal["main", "fast"]
T = TypeVar("T", bound=BaseModel)

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class InvalidJSONError(LLMError):
    """The model answered, but not with a usable JSON object. `complete_json` asks once more."""

    def __init__(self, message: str, more_tokens: bool = False):
        super().__init__(message)
        self.more_tokens = more_tokens  # the reply was cut off at max_tokens: retry with a larger budget


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


def json_shape(schema: type[BaseModel]) -> str:
    """A compact example object for the prompt. Weaker models echo a raw JSON Schema back instead of filling it."""
    root = schema.model_json_schema()
    defs = root.get("$defs", {})

    def example(node: dict):
        if "$ref" in node:
            return example(defs[node["$ref"].rsplit("/", 1)[-1]])
        if "anyOf" in node:  # Optional[X]: show X, keeping the field's description
            inner = next((o for o in node["anyOf"] if o.get("type") != "null"), {})
            return example({"description": node.get("description", ""), **inner})
        kind = node.get("type")
        if kind == "object":
            return {k: example(v) for k, v in node.get("properties", {}).items()}
        if kind == "array":
            return [example(node.get("items", {}))]
        if kind == "boolean":
            return node.get("default", True)
        if kind in ("integer", "number"):
            return node.get("default", 0)
        if "enum" in node:
            return "one of: " + ", ".join(map(str, node["enum"]))
        return node.get("description") or "..."

    return json.dumps(example(root))


def parse_json_reply[M: BaseModel](text: str, schema: type[M]) -> M:
    """Validate the first JSON object in a reply, tolerating code fences and prose around it."""
    decoder = json.JSONDecoder()
    first_error: Exception | None = None  # the first error is the most telling one
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text, m.start())
        except json.JSONDecodeError as e:
            first_error = first_error or e
            continue
        candidates = [obj]
        if len(obj) == 1 and isinstance(inner := next(iter(obj.values())), dict):
            candidates.append(inner)  # {"_Reason": {"reason": ...}}: one key wrapped around the payload
        for candidate in candidates:
            try:
                return schema.model_validate(candidate)
            except ValidationError as e:
                first_error = first_error or e
        break  # the first complete object is the answer; objects nested inside it are not
    reason = first_error or ("empty reply" if not text.strip() else "no JSON object in the reply")
    raise InvalidJSONError(f"model returned invalid JSON for {schema.__name__}: {reason}")


@dataclass
class Usage:
    calls: int = 0
    failures: int = 0  # provider errors; the calling agent falls back to its offline path
    retries: int = 0  # unusable JSON replies asked once more (each retry is also counted in `calls`)
    failure_reasons: dict[str, int] = field(default_factory=dict)  # error message -> count
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

    def fail(self, error: Exception) -> None:
        self.failures += 1
        reason = str(error)[:300]
        self.failure_reasons[reason] = self.failure_reasons.get(reason, 0) + 1
        log.warning("LLM call failed, using the offline path: %s", reason)


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
        try:
            out = self._complete(system, prompt, tier=tier, max_tokens=max_tokens)
        except LLMError as e:
            self.usage.fail(e)
            raise
        self._cache_put(key, out)
        return out

    def complete_json(
        self, system: str, prompt: str, schema: type[T], *, tier: Tier = "main", max_tokens: int = 8000
    ) -> T:
        assert_redacted(prompt)
        key = self._cache_key("json", system, prompt, tier, schema.__name__)
        if (hit := self._cache_get(key)) is not None:
            return schema.model_validate_json(hit)
        try:
            out = self._complete_json_with_retry(system, prompt, schema, tier, max_tokens)
        except LLMError as e:
            self.usage.fail(e)
            raise
        self._cache_put(key, out.model_dump_json())
        return out

    def _complete_json_with_retry(self, system: str, prompt: str, schema: type[T], tier: Tier, max_tokens: int) -> T:
        """One corrective retry: weak models sometimes echo the schema, break the JSON or answer with nothing.
        A call that still fails counts as one failure; the retry itself shows in `usage.retries`."""
        try:
            return self._complete_json(system, prompt, schema, tier=tier, max_tokens=max_tokens)
        except InvalidJSONError as e:
            self.usage.retries += 1
            log.info("retrying an unusable JSON reply: %s", str(e)[:300])
            retry = (f"{prompt}\n\nYour previous reply could not be used ({str(e)[:300]}). "
                     "Reply with only the JSON object, with real values filled in.")
            assert_redacted(retry)  # the error quotes the model's own reply
            budget = max_tokens * 2 if e.more_tokens else max_tokens
            return self._complete_json(system, retry, schema, tier=tier, max_tokens=budget)

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
