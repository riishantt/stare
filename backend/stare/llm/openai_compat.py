"""OpenAI-compatible provider, intended for a local model server (Ollama, llama.cpp, vLLM).

Only used when STARE_LLM_PROVIDER=openai_compat and STARE_LLM_BASE_URL is set, e.g.
STARE_LLM_BASE_URL=http://localhost:11434/v1 for a free local Ollama model.
"""

from __future__ import annotations

import json
import re

from stare.llm.base import ChatModel, LLMError, T, Tier


class OpenAICompatModel(ChatModel):
    provider = "openai_compat"

    def __init__(self, main_model: str, fast_model: str, base_url: str, api_key: str = "", cache_dir=None):
        super().__init__(main_model, fast_model, cache_dir)
        if not base_url:
            raise LLMError("STARE_LLM_BASE_URL is required for the openai_compat provider")
        from openai import OpenAI  # optional dependency

        self.client = OpenAI(base_url=base_url, api_key=api_key or "not-needed")

    def _chat(self, system: str, prompt: str, tier: Tier, max_tokens: int, json_mode: bool) -> str:
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
            raise LLMError(f"local model server error: {e}") from e
        usage = getattr(resp, "usage", None)
        self.usage.add(model, getattr(usage, "prompt_tokens", 0), getattr(usage, "completion_tokens", 0), 0.0)
        return resp.choices[0].message.content or ""

    def _complete(self, system: str, prompt: str, *, tier: Tier, max_tokens: int) -> str:
        return self._chat(system, prompt, tier, max_tokens, json_mode=False)

    def _complete_json(self, system: str, prompt: str, schema: type[T], *, tier: Tier, max_tokens: int) -> T:
        system = f"{system}\n\nReply with one JSON object matching this JSON Schema:\n{json.dumps(schema.model_json_schema())}"
        text = self._chat(system, prompt, tier, max_tokens, json_mode=True)
        match = re.search(r"\{.*\}", text, re.S)
        try:
            return schema.model_validate(json.loads(match.group(0) if match else text))
        except (json.JSONDecodeError, ValueError) as e:
            raise LLMError(f"model returned invalid JSON for {schema.__name__}: {e}") from e
