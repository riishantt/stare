"""Claude provider (Anthropic Python SDK). Only used when STARE_LLM_PROVIDER=anthropic.

Receives redacted text only. Uses structured outputs for JSON responses and the server-side refusal
fallback so a safety-classifier refusal is retried on a fallback model instead of failing the run.
"""

from __future__ import annotations

import json

from stare.llm.base import ChatModel, LLMError, T, Tier

# USD per million tokens (input, output). Used for the per-run cost shown in the audit log.
_PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicModel(ChatModel):
    provider = "anthropic"

    def __init__(self, main_model: str, fast_model: str, api_key: str = "", cache_dir=None, effort: str = "medium"):
        super().__init__(main_model, fast_model, cache_dir)
        import anthropic  # optional dependency

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.effort = effort

    def _create(self, system: str, prompt: str, tier: Tier, max_tokens: int, output_config: dict):
        model = self.model_for(tier)
        try:
            response = self.client.beta.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config=output_config,
                betas=[_FALLBACK_BETA],
                fallbacks="default",
            )
        except self._anthropic.RateLimitError as e:
            raise LLMError(f"rate limited by the Claude API: {e}") from e
        except self._anthropic.APIStatusError as e:
            raise LLMError(f"Claude API error {e.status_code}: {e.message}") from e
        except self._anthropic.APIConnectionError as e:
            raise LLMError(f"cannot reach the Claude API: {e}") from e

        if response.stop_reason == "refusal":
            raise LLMError("the model declined this request")
        u = response.usage
        p_in, p_out = _PRICES.get(model, (4.00, 20.00))
        cost = (u.input_tokens * p_in + u.output_tokens * p_out) / 1_000_000
        self.usage.add(model, u.input_tokens, u.output_tokens, cost)
        text = "".join(b.text for b in response.content if b.type == "text")
        if response.stop_reason == "max_tokens":
            raise LLMError("response truncated at max_tokens")
        return text

    def _complete(self, system: str, prompt: str, *, tier: Tier, max_tokens: int) -> str:
        return self._create(system, prompt, tier, max_tokens, {"effort": self.effort})

    def _complete_json(self, system: str, prompt: str, schema: type[T], *, tier: Tier, max_tokens: int) -> T:
        fmt = {"type": "json_schema", "schema": _strict_schema(schema.model_json_schema())}
        text = self._create(system, prompt, tier, max_tokens, {"effort": self.effort, "format": fmt})
        try:
            return schema.model_validate(json.loads(text))
        except (json.JSONDecodeError, ValueError) as e:
            raise LLMError(f"model returned invalid JSON for {schema.__name__}: {e}") from e


def _strict_schema(schema: dict) -> dict:
    """Structured outputs require additionalProperties: false on every object."""

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object" or "properties" in node:
                node.setdefault("additionalProperties", False)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        return node

    return walk(json.loads(json.dumps(schema)))
