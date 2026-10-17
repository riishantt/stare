"""Paragraph-aware text chunker (tokens approximated by whitespace-separated words)."""

from __future__ import annotations

import re

_PARA = re.compile(r"\n\s*\n")
_SENT = re.compile(r"(?<=[.;?!])\s+(?=[A-Z(\"“])")
_WORD = re.compile(r"\S+")


def _ntok(s: str) -> int:
    return len(_WORD.findall(s))


def _split_units(text: str, max_tokens: int) -> list[tuple[int, int, int]]:
    """Split text into (start, end, n_tokens) units, none larger than max_tokens."""
    units: list[tuple[int, int, int]] = []

    def add_span(a: int, b: int) -> None:
        seg = text[a:b]
        n = _ntok(seg)
        if n == 0:
            return
        if n <= max_tokens:
            units.append((a, b, n))
            return
        words = list(_WORD.finditer(seg))
        for i in range(0, len(words), max_tokens):
            grp = words[i : i + max_tokens]
            units.append((a + grp[0].start(), a + grp[-1].end(), len(grp)))

    pos = 0
    paras = [(m.start(), m.end()) for m in _PARA.finditer(text)]
    bounds = []
    for s, e in paras:
        bounds.append((pos, s))
        pos = e
    bounds.append((pos, len(text)))
    for a, b in bounds:
        seg = text[a:b]
        if _ntok(seg) <= max_tokens:
            add_span(a, b)
            continue
        sp = 0
        for m in _SENT.finditer(seg):
            add_span(a + sp, a + m.start())
            sp = m.end()
        add_span(a + sp, b)
    return units


def chunk_text(text: str, max_tokens: int = 350, overlap: int = 60) -> list[tuple[int, str]]:
    """Return [(char_start, chunk_text)]. Chunks pack whole paragraphs (or sentences when a paragraph is
    too long) up to `max_tokens`; consecutive chunks share roughly `overlap` tokens of trailing context."""
    if not text or not text.strip():
        return []
    max_tokens = max(1, max_tokens)
    overlap = max(0, min(overlap, max_tokens // 2))
    units = _split_units(text, max_tokens)
    chunks: list[tuple[int, str]] = []
    i = 0
    while i < len(units):
        j, total = i, 0
        while j < len(units) and (total + units[j][2] <= max_tokens or j == i):
            total += units[j][2]
            j += 1
        chunks.append((units[i][0], text[units[i][0] : units[j - 1][1]]))
        if j >= len(units):
            break
        k, back = j, 0
        while k - 1 > i and back + units[k - 1][2] <= overlap:
            k -= 1
            back += units[k][2]
        i = k
    return chunks
