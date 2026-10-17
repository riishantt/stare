"""Reciprocal Rank Fusion (Cormack, Clarke & Buettcher, SIGIR 2009)."""

from __future__ import annotations


def rrf(rankings: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    """Fuse ranked id lists: score(d) = sum over lists of 1 / (k + rank), rank starting at 1.

    Returns (id, score) best first; ties keep first-seen order.
    """
    scores: dict[int, float] = {}
    for ranking in rankings:
        seen: set[int] = set()
        rank = 0
        for item in ranking:
            if item in seen:
                continue
            seen.add(item)
            rank += 1
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: -kv[1])  # sorted() is stable
