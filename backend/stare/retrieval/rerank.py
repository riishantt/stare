"""Rerankers. Default is a cheap lexical reranker; a cross-encoder is optional (lazy, downloads a model)."""

from __future__ import annotations

import math
from collections import Counter
from typing import Protocol

from stare.retrieval.tokenize import reference_tokens, tokenize
from stare.schemas import RetrievedChunk

RULE_PHRASES = (
    "must show",
    "must establish",
    "prima facie",
    "we hold",
    "we conclude",
    "burden",
    "to prevail",
    "elements",
    "but-for",
    "the plaintiff must",
)


class Reranker(Protocol):
    def rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]: ...


class NoReranker:
    def rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        return list(chunks)


class LexicalReranker:
    """score = 0.45 * BM25-style overlap (idf from the candidate set) + 0.20 * query-bigram matches
    + 0.20 * query cites/sections present + 0.10 * fused-rank prior + 0.05 rule-statement boost."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b

    def rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        if not chunks:
            return []
        q_toks = tokenize(query)
        q_terms = set(q_toks)
        q_refs = set(reference_tokens(query))
        words = [t for t in q_toks if not t.startswith(("cite:", "sec:"))]
        q_bigrams = set(zip(words, words[1:], strict=False))

        docs = [tokenize(c.text) for c in chunks]
        n = len(docs)
        avgdl = sum(len(d) for d in docs) / n or 1.0
        df = Counter(t for d in docs for t in set(d) if t in q_terms)
        idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        max_rrf = max((c.rrf_score for c in chunks), default=0.0) or 1.0

        raw: list[float] = []
        parts: list[tuple[float, float, float]] = []
        for c, d in zip(chunks, docs, strict=True):
            tf = Counter(d)
            norm = self.k1 * (1 - self.b + self.b * len(d) / avgdl)
            raw.append(sum(idf[t] * tf[t] * (self.k1 + 1) / (tf[t] + norm) for t in idf if t in tf))
            dw = [t for t in d if not t.startswith(("cite:", "sec:"))]
            big = set(zip(dw, dw[1:], strict=False)) & q_bigrams
            bigram = len(big) / len(q_bigrams) if q_bigrams else 0.0
            ref = len(q_refs & set(d)) / len(q_refs) if q_refs else 0.0
            parts.append((bigram, ref, 0.05 if c.kind == "opinion" and _states_rule(c.text) else 0.0))
        top = max(raw) or 1.0

        scored = []
        for c, lex, (bigram, ref, rule) in zip(chunks, raw, parts, strict=True):
            score = 0.45 * lex / top + 0.20 * bigram + 0.20 * ref + 0.10 * c.rrf_score / max_rrf + rule
            scored.append(c.model_copy(update={"rerank_score": round(score, 6)}))
        return sorted(scored, key=lambda c: -(c.rerank_score or 0.0))


def _states_rule(text: str) -> bool:
    low = text.lower()
    return any(p in low for p in RULE_PHRASES)


class CrossEncoderReranker:
    """sentence-transformers CrossEncoder (lazy import; downloads the model on first use)."""

    def __init__(self, model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model
        self._model = None

    def rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        if not chunks:
            return []
        if self._model is None:
            from sentence_transformers import CrossEncoder  # optional dependency

            self._model = CrossEncoder(self.model_name)
        scores = self._model.predict([(query, c.text) for c in chunks])
        scored = [c.model_copy(update={"rerank_score": float(s)}) for c, s in zip(chunks, scores, strict=True)]
        return sorted(scored, key=lambda c: -(c.rerank_score or 0.0))


def get_reranker(settings) -> Reranker:
    if settings.reranker == "cross_encoder":
        return CrossEncoderReranker(settings.reranker_model)
    if settings.reranker == "none":
        return NoReranker()
    return LexicalReranker()
