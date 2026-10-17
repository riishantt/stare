"""Reporter and case-name normalisation (shared by the parser, the index and Gate 2)."""

from __future__ import annotations

import re
from functools import lru_cache

from rapidfuzz import fuzz

_KEY_STRIP = re.compile(r"[\s.'’`()]")


def _key(s: str) -> str:
    return _KEY_STRIP.sub("", s).lower()


@lru_cache(maxsize=1)
def _reporter_map() -> dict[str, str]:
    """key -> canonical edition name. Variations first, real editions override them."""
    import reporters_db

    m: dict[str, str] = {}
    for entries in reporters_db.REPORTERS.values():
        for entry in entries:
            for var, edition in entry.get("variations", {}).items():
                m.setdefault(_key(var), edition)
    for entries in reporters_db.REPORTERS.values():
        for entry in entries:
            for edition in entry.get("editions", {}):
                m[_key(edition)] = edition
    m["wl"] = "WL"
    m["uscfedappx"] = "F. App'x"
    return m


def normalize_reporter(reporter: str) -> str:
    """'F. 3d' / 'F.3d.' -> 'F.3d'; 'U. S.' -> 'U.S.'; 'S.Ct.' -> 'S. Ct.'; 'Fed. Appx.' -> "F. App'x"."""
    reporter = (reporter or "").strip()
    return _reporter_map().get(_key(reporter), reporter)


def reporter_key(reporter: str) -> str:
    """Comparison key that is identical for every spelling of the same reporter."""
    return _key(normalize_reporter(reporter))


# ----------------------------------------------------------------------------------------------
# Case names
# ----------------------------------------------------------------------------------------------

_ABBREV = {
    "univ": "university", "tex": "texas", "sw": "southwestern", "med": "medical", "ctr": "center",
    "cir": "circuit", "dept": "department", "dep": "department", "assn": "association",
    "ass": "association", "bros": "brothers", "intl": "international", "natl": "national",
    "mfg": "manufacturing", "ky": "kentucky", "fla": "florida", "ill": "illinois",
    "ga": "georgia", "cal": "california", "mass": "massachusetts", "penn": "pennsylvania",
    "pa": "pennsylvania", "wash": "washington", "mich": "michigan", "ind": "indiana",
    "ala": "alabama", "miss": "mississippi", "okla": "oklahoma", "ariz": "arizona",
    "colo": "colorado", "conn": "connecticut", "dist": "district", "comm": "commission",
    "commn": "commission", "commr": "commissioner", "emp": "employment", "empl": "employment",
    "opportunity": "opportunity", "eeoc": "equal employment opportunity commission",
    "govt": "government", "gov": "government", "hosp": "hospital", "inst": "institute",
    "ins": "insurance", "indus": "industries", "indust": "industries", "mgmt": "management",
    "serv": "service", "servs": "services", "sys": "system", "sch": "school", "st": "state",
    "tel": "telephone", "transp": "transportation", "trans": "transportation",
    "cnty": "county", "co": "company", "corp": "corporation", "inc": "", "ltd": "", "llc": "",
    "llp": "", "lp": "", "plc": "", "pc": "", "et": "", "al": "", "na": "", "nka": "", "fka": "",
    "etc": "", "the": "", "of": "", "and": "", "for": "", "a": "", "an": "", "in": "", "on": "",
    "ex": "", "rel": "", "re": "", "no": "",
    "united": "united", "u.s": "united states", "us": "united states", "usa": "united states",
}
# "Company"/"Corporation" are noise too; map after expansion
_NOISE = {"company", "corporation", "incorporated", "limited", "co", "corp", "inc", "ltd", "llc"}
_V_SPLIT = re.compile(r"\s+(?:v\.?|vs\.?|versus)\s+", re.IGNORECASE)
_MULTI = {"air lines": "airlines", "air line": "airline", "u s": "united states"}


def _tokens(side: str) -> list[str]:
    s = side.lower().replace("&", " and ").replace("’", "'")
    s = re.sub(r"\bu\.\s?s\.(?:a\.)?", " united states ", s)
    for k, v in _MULTI.items():
        s = s.replace(k, v)
    s = re.sub(r"['`]", "", s)
    out: list[str] = []
    for tok in re.findall(r"[a-z0-9]+", s):
        tok = _ABBREV.get(tok, tok)
        for t in tok.split():
            if t and t not in _NOISE:
                out.append(t)
    return out


def split_case_name(name: str) -> list[str]:
    parts = _V_SPLIT.split(re.sub(r"\s+", " ", name or "").strip(), maxsplit=1)
    return [p for p in parts if p.strip()]


def normalize_case_name(name: str) -> str:
    """Canonical comparison form: 'tokens of side1 v tokens of side2'."""
    return " v ".join(" ".join(_tokens(p)) for p in split_case_name(name))


def case_name_similarity(a: str, b: str) -> float:
    """0..1. Both names have two parties: first party weighs most (0.6), second 0.25, whole name 0.15.
    A one-sided name (e.g. 'Nassar') is compared with every party of the other name."""
    sa, sb = split_case_name(a), split_case_name(b)
    ta = [" ".join(sorted(set(_tokens(p)))) for p in sa]
    tb = [" ".join(sorted(set(_tokens(p)))) for p in sb]
    ta, tb = [t for t in ta if t], [t for t in tb if t]
    if not ta or not tb:
        return 0.0
    if len(ta) == 1 or len(tb) == 1:
        whole_a, whole_b = " ".join(ta), " ".join(tb)
        best = max(fuzz.token_set_ratio(x, y) for x in ta + [whole_a] for y in tb + [whole_b])
        return round(best / 100, 4)
    first = fuzz.token_set_ratio(ta[0], tb[0])
    second = fuzz.token_set_ratio(ta[1], tb[1])
    whole = fuzz.token_sort_ratio(" ".join(ta), " ".join(tb))
    score = (0.6 * first + 0.25 * second + 0.15 * whole) / 100
    if first < 40:  # different lead party: a different case, whatever the defendant is
        score = min(score, 0.45)
    return round(score, 4)
