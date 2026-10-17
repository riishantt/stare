"""Legal-aware tokenizer shared by BM25, the LSA embedder and the lexical reranker.

Beyond lowercasing, light stopword removal and suffix stemming it emits *reference tokens* so that
exact citations match exactly:

* reporter cites   "411 U.S. 792"        -> ``cite:411:us:792`` (plus the plain tokens 411, u.s, 792)
* statute sections "§ 12112(b)(5)(A)"    -> ``sec:12112`` ``sec:12112(b)`` ``sec:12112(b)(5)`` ``sec:12112(b)(5)(a)``
  also from "42 U.S.C. 2000e-3" and "29 C.F.R. § 1630.2"; a query for the base section matches
  chunks citing any subsection, a query for a subsection matches that subsection's text.
"""

from __future__ import annotations

import re
import unicodedata

STOPWORDS = frozenset(
    """a an and are as at be been but by for from had has have he her his if in into is it its of on or
    our she so such than that the their them then there these they this those to was we were which who
    will with would not no also may can could should shall any all each other""".split()
)

_NUM = r"\d+[a-z]*(?:[-.]\d+[a-z]*)*"
_SUBS = r"((?:\([a-z0-9]{1,4}\))*)"
_REPORTER = (
    r"u\.\s?s\.|s\.\s?ct\.|l\.\s?ed\.(?:\s?2d)?|f\.\s?(?:2d|3d|4th)|f\.\s?supp\.(?:\s?[23]d)?|"
    r"f\.\s?app'?x|fed\.\s?app'?x"
)
_CITE_RE = re.compile(rf"\b(\d{{1,4}})\s+({_REPORTER})\s+(\d{{1,5}})\b")
_SECTION_RES = (
    re.compile(rf"§§?\s*({_NUM}){_SUBS}"),
    re.compile(rf"\b\d+\s+(?:u\.?s\.?c\.?|c\.?f\.?r\.?)(?:\s+sec(?:tions?|s?\.))?\s+({_NUM}){_SUBS}"),
)
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-.][a-z0-9]+)*")


def _stem(w: str) -> str:
    """Very light suffix stripper; only needs to be consistent between index and query."""
    n = len(w)
    if n <= 3:
        return w
    if w.endswith("ies") and n > 4:
        return w[:-3] + "y"
    if w.endswith("sses"):
        return w[:-2]
    if w.endswith("ing") and n > 5:
        w = w[:-3]
        return w[:-1] if len(w) > 3 and w[-1] == w[-2] else w
    if w.endswith("ed") and n > 4:
        w = w[:-2]
        return w[:-1] if len(w) > 3 and w[-1] == w[-2] else w
    if w.endswith("ly") and n > 5:
        return w[:-2]
    if w.endswith("es") and n > 4 and w[-3] in "sxz":
        return w[:-2]
    if w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def _norm_reporter(r: str) -> str:
    return re.sub(r"[^a-z0-9]", "", r)


def reference_tokens(text: str) -> list[str]:
    """Reporter-cite and statute-section tokens found in ``text`` (case-insensitive)."""
    t = unicodedata.normalize("NFKC", text).lower().replace("’", "'")
    out: list[str] = []
    for m in _CITE_RE.finditer(t):
        out.append(f"cite:{m.group(1)}:{_norm_reporter(m.group(2))}:{m.group(3)}")
    for rx in _SECTION_RES:
        for m in rx.finditer(t):
            base = m.group(1)
            out.append(f"sec:{base}")
            acc = base
            for sub in re.findall(r"\([a-z0-9]{1,4}\)", m.group(2)):
                acc += sub
                out.append(f"sec:{acc}")
    return out


def tokenize(text: str) -> list[str]:
    """Tokens for indexing and querying. Reference tokens come first, then word tokens."""
    out = reference_tokens(text)
    t = unicodedata.normalize("NFKC", text).lower().replace("’", "'").replace("'", "")
    for raw in _TOKEN_RE.findall(t):
        if len(raw) < 2:
            continue
        if any(c.isdigit() for c in raw):
            out.append(raw)
            if "-" in raw:  # "2000e-3" also matches a bare "2000e"
                out.extend(p for p in raw.split("-") if len(p) >= 2)
        elif "-" in raw:
            parts = [p for p in raw.split("-") if len(p) >= 2 and p not in STOPWORDS]
            out.append(raw)
            out.extend(_stem(p) for p in parts)
        elif "." in raw:  # abbreviations: u.s, u.s.c
            out.append(raw)
        elif raw not in STOPWORDS:
            out.append(_stem(raw))
    return out
