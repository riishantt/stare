"""Evaluation metrics (Table 29)."""

from __future__ import annotations

import re
from collections.abc import Iterable

import numpy as np

_CITE = re.compile(r"\s+")


def norm_cite(cite: str) -> str:
    """'411 U. S. 792' -> '411 U.S. 792' style key for comparing citations."""
    c = cite.replace("U. S.", "U.S.").replace("S.Ct.", "S. Ct.").replace("F. 2d", "F.2d").replace("F. 3d", "F.3d")
    c = c.replace("F. 4th", "F.4th").replace("§§", "§")
    return _CITE.sub(" ", c).strip().lower()


def recall_at_k(ranked_cites: list[str], expected: Iterable[str], k: int = 10) -> float | None:
    expected = {norm_cite(e) for e in expected}
    if not expected:
        return None
    top = {norm_cite(c) for c in ranked_cites[:k]}
    return len(expected & top) / len(expected)


def p95(values: list[float]) -> float | None:
    return float(np.percentile(values, 95)) if values else None


def mean(values: list[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None
