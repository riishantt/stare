"""LLM provider factory."""

from __future__ import annotations

from stare.config import Settings, get_settings
from stare.llm.base import ChatModel, LLMError, UnredactedTextError, assert_redacted
from stare.llm.offline import OfflineModel


def get_llm(settings: Settings | None = None) -> ChatModel:
    s = settings or get_settings()
    cache = s.cache_dir / "llm" if s.llm_cache else None
    if s.llm_provider == "anthropic":
        from stare.llm.anthropic_llm import AnthropicModel

        return AnthropicModel(s.llm_model, s.llm_fast_model, api_key=s.llm_api_key, cache_dir=cache)
    if s.llm_provider == "openai_compat":
        from stare.llm.openai_compat import OpenAICompatModel

        return OpenAICompatModel(s.llm_model, s.llm_fast_model, s.llm_base_url, s.llm_api_key, cache_dir=cache)
    return OfflineModel()


__all__ = ["ChatModel", "LLMError", "OfflineModel", "UnredactedTextError", "assert_redacted", "get_llm"]
