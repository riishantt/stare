"""Legal-text sentence splitting that does not break on reporter abbreviations ("U. S.", "Corp. v.", "F. 3d")."""

from __future__ import annotations

import re

_ABBREV = {
    "u", "s", "v", "vs", "corp", "co", "inc", "ltd", "llc", "no", "nos", "cir", "dist", "ct", "app", "supp", "f",
    "l", "ed", "e.g", "i.e", "mr", "ms", "mrs", "dr", "jr", "sr", "st", "dept", "assn", "ass'n", "univ", "sw",
    "med", "ctr", "tex", "cal", "cnty", "r", "ry", "bros", "et", "al", "id", "cf", "p", "pp", "n", "nn", "fed",
    "reg", "stat", "pub", "am", "nat'l", "int'l", "mfg", "ky", "ill", "fla", "ga", "la", "miss", "ala", "ariz",
    "colo", "conn", "del", "md", "mass", "mich", "minn", "mo", "neb", "nev", "okla", "or", "pa", "tenn", "va",
    "wash", "wis", "wyo", "gov't", "govt", "comm'n", "sys", "servs", "serv", "auth", "bd", "educ", "hosp",
    "indus", "mgmt", "prods", "sch", "transp", "u.s", "s.ct", "art", "cl", "ch", "sec", "secs", "seq", "supra",
    "infra", "rev", "ann", "approx", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov",
    "dec", "ibid",
}
_BOUNDARY = re.compile(r"[.!?][\"”’)\]]*\s+")


def split_sentences(text: str) -> list[str]:
    text = " ".join(text.split())
    out: list[str] = []
    start = 0
    for m in _BOUNDARY.finditer(text):
        end = m.end()
        nxt = text[end:end + 1]
        if not nxt or not (nxt.isupper() or nxt in "\"“("):
            continue  # next word is lowercase or a number: not a sentence break
        before = text[start:m.start() + 1].rsplit(" ", 1)[-1].lower().rstrip(".").lstrip("(\"“")
        if before in _ABBREV or (len(before) == 1 and before.isalpha()):
            continue
        out.append(text[start:m.end()].strip())
        start = end
    if start < len(text):
        out.append(text[start:].strip())
    return [s for s in out if s]


# ---------------------------------------------------------------------------------------------- opinion parts
# Opinion text stores the opinion of the court first; each separate opinion starts with a marker line such as
# "[DISSENTING OPINION — Justice Ginsburg]". Quotes and holdings must come from the opinion of the court.

PART_LABELS = {
    "dissent": "DISSENTING",
    "concurrence": "CONCURRING",
    "concurring-in-part-and-dissenting-in-part": "CONCURRING IN PART AND DISSENTING IN PART",
}
PART_MARKER = re.compile(r"^\[((?:[A-Z]+ )*?(?:DISSENTING|CONCURRING|SEPARATE)(?: [A-Z ]+)?) OPINION(?: — [^\]]*)?\]$", re.M)


def part_marker(opinion_type: str, author: str | None = None) -> str:
    label = PART_LABELS.get(opinion_type, "SEPARATE")
    return f"[{label} OPINION" + (f" — {author.strip()}" if author and author.strip() else "") + "]"


def majority_text(text: str) -> str:
    """The opinion of the court: everything before the first separate-opinion marker."""
    m = PART_MARKER.search(text or "")
    return text[: m.start()] if m else (text or "")


def part_at(text: str, offset: int) -> str:
    """'majority', 'dissent', 'concurrence' or 'separate' for a character offset."""
    part = "majority"
    for m in PART_MARKER.finditer(text or ""):
        if m.start() > offset:
            break
        label = m.group(1)
        part = "dissent" if "DISSENT" in label and "CONCURRING" not in label else (
            "concurrence" if label == "CONCURRING" else "separate")
    return part


_SEPARATE_HEADER = re.compile(
    r"^(?:(?:mr\.|mrs\.|ms\.)\s+)?(?:chief\s+)?(?:justice|judge)\s+[a-z'’\-]+.{0,250}?,\s*(dissenting|concurring)[^\n]{0,80}$"
    r"|^[A-Z][A-Za-z'’\-]+,\s*(?:Chief\s+)?(?:Circuit|District)\s+Judge,?\s+(dissenting|concurring)[^\n]{0,80}$",
    re.IGNORECASE | re.MULTILINE,
)


def mark_separate_opinions(text: str) -> str:
    """Insert part markers before separate-opinion headers that source data left inside the court's opinion,
    e.g. "Justice GINSBURG, with whom ... join, dissenting." (CAP sometimes merges them into the majority)."""

    def repl(m: re.Match) -> str:
        header = m.group(0)
        kind = (m.group(1) or m.group(2) or "").lower()
        both = "dissent" in header.lower() and "concur" in header.lower()
        opinion_type = "concurring-in-part-and-dissenting-in-part" if both else ("dissent" if kind == "dissenting" else "concurrence")
        author = re.split(r",", header, maxsplit=1)[0].strip()
        return f"{part_marker(opinion_type, author)}\n{header}"

    return _SEPARATE_HEADER.sub(repl, text or "")


_DELIVERED = re.compile(r"^[^\n]{0,80}\bdelivered the opinion (?:of|for) (?:the|a unanimous) Court[^\n]*$", re.MULTILINE)


def strip_syllabus(text: str) -> str:
    """Drop the Reporter's syllabus ("Syllabus ... Held: ...") that precedes some Supreme Court opinions:
    it is not part of the opinion and must never be quoted as the Court's words."""
    if "syllabus" not in (text or "")[:600].lower():
        return text
    m = _DELIVERED.search(text)
    return text[m.end():].lstrip() if m else text
