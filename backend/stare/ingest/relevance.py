"""Cheap relevance filter for bulk imports: keep employment-discrimination opinions."""

from __future__ import annotations

import re

_STRONG = re.compile(
    r"title vii|2000e|civil rights act of 1964|americans with disabilities act|\bADEA\b|"
    r"age discrimination in employment|12101|12112|\b29 U\.?S\.?C\.? ?§? ?62[1-9]|equal employment opportunity",
    re.IGNORECASE,
)


def is_employment_text(text: str, min_hits: int = 2) -> bool:
    return len(_STRONG.findall(text[:200_000])) >= min_hits
