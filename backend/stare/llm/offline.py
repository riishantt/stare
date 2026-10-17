"""Deterministic offline provider.

It never generates legal content itself: agents detect `is_offline` and run their rule-based paths
(template queries, extractive memo drafting from verified passages). Calling it directly is a bug.
"""

from __future__ import annotations

from stare.llm.base import ChatModel, LLMError, T, Tier


class OfflineModel(ChatModel):
    provider = "offline"
    is_offline = True

    def __init__(self, *args, **kwargs):
        super().__init__(main_model="", fast_model="", cache_dir=None)

    def _complete(self, system: str, prompt: str, *, tier: Tier, max_tokens: int) -> str:
        raise LLMError("offline provider: agents must use their deterministic path when llm.is_offline")

    def _complete_json(self, system: str, prompt: str, schema: type[T], *, tier: Tier, max_tokens: int) -> T:
        raise LLMError("offline provider: agents must use their deterministic path when llm.is_offline")
