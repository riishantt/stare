"""OpenAI-compatible provider: a local model server (Ollama, llama.cpp, vLLM) or a hosted gateway such as
OpenRouter (STARE_LLM_BASE_URL=https://openrouter.ai/api/v1, free models end in ":free").

Only used when STARE_LLM_PROVIDER=openai_compat and STARE_LLM_BASE_URL is set, e.g.
STARE_LLM_BASE_URL=http://localhost:11434/v1 for a free local Ollama model.
"""

from __future__ import annotations

import json

from stare.llm.base import ChatModel, InvalidJSONError, LLMError, T, Tier, json_shape, parse_json_reply


class OpenAICompatModel(ChatModel):
    provider = "openai_compat"

    def __init__(self, main_model: str, fast_model: str, base_url: str, api_key: str = "", cache_dir=None):
        super().__init__(main_model, fast_model, cache_dir)
        if not base_url:
            raise LLMError("STARE_LLM_BASE_URL is required for the openai_compat provider")
        from openai import OpenAI  # optional dependency

        # Free tiers rate-limit; the SDK retries 429 and 5xx responses with exponential backoff.
        self.client = OpenAI(base_url=base_url, api_key=api_key or "not-needed", max_retries=5, timeout=120)

    def _chat(self, system: str, prompt: str, tier: Tier, max_tokens: int, json_mode: bool) -> tuple[str, str | None]:
        """Returns the reply text and its finish_reason ("length" means max_tokens was reached)."""
        model = self.model_for(tier)
        kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
        try:
            resp = self.client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                **kwargs,
            )
        except Exception as e:  # the openai SDK raises many transport-specific errors
            raise LLMError(f"model server error: {e}") from e
        usage = getattr(resp, "usage", None)
        self.usage.add(model, getattr(usage, "prompt_tokens", 0), getattr(usage, "completion_tokens", 0), 0.0)
        if not resp.choices:  # some gateways answer 200 with an error body and no choices
            raise LLMError(f"model server returned no choices: {getattr(resp, 'error', None)}")
        # Only `content` is the answer; a reasoning model's hidden reasoning (if returned at all) is not.
        choice = resp.choices[0]
        return choice.message.content or "", getattr(choice, "finish_reason", None)

    def _complete(self, system: str, prompt: str, *, tier: Tier, max_tokens: int) -> str:
        return self._chat(system, prompt, tier, max_tokens, json_mode=False)[0]

    def _complete_json(self, system: str, prompt: str, schema: type[T], *, tier: Tier, max_tokens: int) -> T:
        shape = json_shape(schema)
        system = (f"{system}\n\nReply with only one JSON object of this shape, replacing each placeholder value "
                  f"(lists may hold any number of entries). Do not repeat this description.\n{shape}")
        text, finish = self._chat(system, prompt, tier, max_tokens, json_mode=True)
        try:
            out = parse_json_reply(text, schema)
            if out.model_dump(mode="json") == json.loads(shape):
                raise InvalidJSONError(f"model returned invalid JSON for {schema.__name__}: the example was echoed back")
            return out
        except InvalidJSONError as e:
            if finish != "length":
                raise
            # Reasoning models can spend the whole budget on hidden reasoning and return no content.
            raise InvalidJSONError(f"reply for {schema.__name__} cut off at max_tokens={max_tokens} "
                                   f"({'empty' if not text.strip() else 'incomplete JSON'})", more_tokens=True) from e
