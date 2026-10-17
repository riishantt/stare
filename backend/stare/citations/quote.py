"""Quote normalisation and fuzzy matching (Gate 3)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from rapidfuzz import fuzz

_ELLIPSIS = re.compile(r"\s*(?:\.\s?\.\s?\.(?:\s?\.)?|…)\s*")
_ALTER_DROP = re.compile(r"\[\s*(?:sic|emphasis[^\]]*|internal[^\]]*|citation[^\]]*|footnote[^\]]*|alteration[^\]]*|italics[^\]]*)\]", re.IGNORECASE)
_FOOTNOTE = re.compile(r"(?<=[a-z][.,;:\"”’')])\d{1,2}(?=\s|$)")
_SUPERSCRIPT = str.maketrans("", "", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def normalize(text: str) -> str:
    """Lowercase, straight quotes, dashes, de-hyphenated line breaks, no footnote markers or
    bracketed alterations, punctuation reduced to single spaces. Used on both sides of a comparison."""
    t = unicodedata.normalize("NFKC", text or "").translate(_SUPERSCRIPT)
    t = t.replace("­", "")
    t = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", t)  # hyphenation across a line break
    t = _ALTER_DROP.sub(" ", t)
    t = re.sub(r"\[([^\]]*)\]", r"\1", t)  # "[t]he" -> "the"
    t = re.sub(r"(?<!\w)\*\d+\b", " ", t)  # star pagination
    t = _FOOTNOTE.sub("", t)
    t = t.lower()
    t = re.sub(r"[‘’`´]", "'", t)
    t = re.sub(r"[“”]", '"', t)
    t = re.sub(r"['](?=\w)|(?<=\w)[']", "", t)  # employer's -> employers
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return t.strip()


def split_fragments(quote: str) -> list[str]:
    """Quote -> normalised fragments split at ellipses (each must appear, in order)."""
    quote = (quote or "").strip().strip('"“”').strip()
    frags = [normalize(p) for p in _ELLIPSIS.split(quote)]
    return [f for f in frags if f]


@dataclass
class QuoteMatch:
    score: float
    fragments: list[str] = field(default_factory=list)
    matched: str = ""  # best matching passage of the opinion (normalised), for the attorney's diff view

    @property
    def exact(self) -> bool:
        return self.score >= 0.999


def prepare(opinion_text: str) -> str:
    return normalize(opinion_text)


def match_quote(quote: str, opinion_text: str, *, prepared: bool = False) -> QuoteMatch:
    """Similarity 0..1 of a quotation against an opinion. Fragments separated by ellipses are
    matched independently, in order; the score is the length-weighted mean."""
    frags = split_fragments(quote)
    if not frags:
        return QuoteMatch(1.0)
    hay = opinion_text if prepared else normalize(opinion_text)
    if not hay:
        return QuoteMatch(0.0, frags)
    cursor = 0
    total = weight = 0.0
    matched_parts: list[str] = []
    for f in frags:
        w = max(len(f), 1)
        idx = hay.find(f, cursor)
        if idx >= 0:
            s, end = 1.0, idx + len(f)
            matched_parts.append(hay[idx:end])
        else:
            s, start, end = _fuzzy(f, hay[cursor:])
            start += cursor
            end += cursor
            if cursor and s < 0.999:
                # fragment present only before the previous one: out of order
                s_all, _, _ = _fuzzy(f, hay)
                if s_all > s + 0.05:
                    s = min(s, 0.5)
            matched_parts.append(hay[start:end])
        if idx >= 0 or s > 0:
            cursor = max(cursor, end)
        total += s * w
        weight += w
    return QuoteMatch(round(total / weight, 4), frags, " ... ".join(matched_parts))


def _fuzzy(frag: str, hay: str) -> tuple[float, int, int]:
    if not hay:
        return 0.0, 0, 0
    al = fuzz.partial_ratio_alignment(frag, hay)
    if al is None:
        return 0.0, 0, 0
    # extend the window to whole words for readability
    return al.score / 100.0, al.dest_start, al.dest_end


def quote_similarity(quote: str, opinion_text: str) -> float:
    return match_quote(quote, opinion_text).score
