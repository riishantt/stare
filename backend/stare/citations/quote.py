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
QUOTE_SEP = " | "  # joins separate quotations attached to one citation; each is matched on its own
# An ellipsis may omit words, but not ones that reverse the quoted proposition ("is [not] liable").
_NEGATION = frozenset(
    "not no never nor neither none nothing cannot without unless except".split()
    + "isnt arent wasnt werent dont doesnt didnt cant couldnt wont wouldnt shouldnt mustnt neednt hasnt havent hadnt".split()
)
_MIN_FRAGMENT_WORDS = 3  # one or two words around an ellipsis can be found almost anywhere
_MAX_GAP = 1500  # normalised characters an ellipsis may omit (a long paragraph)
_NEGATION_GAP = 300  # a negation inside a short omission (the same sentence or the next) can reverse the quote


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
    quote = (quote or "").replace(QUOTE_SEP, " ... ").strip().strip('"“”').strip()
    frags = [normalize(p) for p in _ELLIPSIS.split(quote)]
    return [f for f in frags if f]


@dataclass
class QuoteMatch:
    score: float
    fragments: list[str] = field(default_factory=list)
    matched: str = ""  # best matching passage of the opinion (normalised), for the attorney's diff view
    concern: str = ""  # why an ellipsis quotation should be read against the opinion even if every fragment matches

    @property
    def exact(self) -> bool:
        return self.score >= 0.999


def prepare(opinion_text: str) -> str:
    return normalize(opinion_text)


def match_quote(quote: str, opinion_text: str, *, prepared: bool = False) -> QuoteMatch:
    """Similarity 0..1 of a quotation against an opinion. Fragments separated by ellipses must appear in
    order; the score is the length-weighted mean. Separate quotations (QUOTE_SEP) are matched independently."""
    hay = opinion_text if prepared else normalize(opinion_text)
    parts = [p for p in (quote or "").split(QUOTE_SEP) if split_fragments(p)]
    if len(parts) <= 1:
        return _match_one(quote, hay)
    ms = [_match_one(p, hay) for p in parts]
    weights = [max(sum(len(f) for f in m.fragments), 1) for m in ms]
    score = sum(m.score * w for m, w in zip(ms, weights, strict=True)) / sum(weights)
    return QuoteMatch(round(score, 4), [f for m in ms for f in m.fragments], " | ".join(m.matched for m in ms),
                      "; ".join(dict.fromkeys(m.concern for m in ms if m.concern)))


def _match_one(quote: str, hay: str) -> QuoteMatch:
    frags = split_fragments(quote)
    if not frags:
        return QuoteMatch(1.0)
    if not hay:
        return QuoteMatch(0.0, frags)
    cursor = 0
    total = weight = 0.0
    matched_parts: list[str] = []
    concerns: list[str] = []
    prev: tuple[str, int, int] | None = None  # previous fragment, where its search began, where its match ends
    for f in frags:
        w = max(len(f), 1)
        lo = cursor
        idx = hay.find(f, cursor)
        if idx >= 0:
            s, start, end = 1.0, idx, idx + len(f)
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
        if prev is not None and s > 0:
            # what the ellipsis leaves out: from the previous fragment's occurrence closest before this one
            p_frag, p_lo, p_end = prev
            j = hay.rfind(p_frag, p_lo, start)
            omitted = hay[(j + len(p_frag)) if j >= 0 else p_end:start]
            neg = next((t for t in omitted.split() if t in _NEGATION), None)
            if neg and len(omitted) <= _NEGATION_GAP:
                concerns.append(f"the text omitted at an ellipsis contains '{neg}'")
            elif len(omitted) > _MAX_GAP:
                concerns.append("the fragments joined by an ellipsis are far apart in the opinion")
        if idx >= 0 or s > 0:
            cursor = max(cursor, end)
            prev = (f, lo, end)
        total += s * w
        weight += w
    if len(frags) > 1 and any(len(f.split()) < _MIN_FRAGMENT_WORDS for f in frags):
        concerns.append(f"a fragment around an ellipsis is shorter than {_MIN_FRAGMENT_WORDS} words")
    return QuoteMatch(round(total / weight, 4), frags, " ... ".join(matched_parts), "; ".join(dict.fromkeys(concerns)))


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
