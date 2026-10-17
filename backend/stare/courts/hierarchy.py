"""Federal court hierarchy: court registry, free-text normalisation and authority ranking (Table 26)."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from stare.config import REPO_DIR
from stare.schemas import AuthorityRank, Court

COURTS_JSON = REPO_DIR / "data" / "courts.json"

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "the District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana",
    "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "PR": "Puerto Rico", "GU": "Guam", "MP": "the Northern Mariana Islands", "VI": "the Virgin Islands",
}
_DIVISIONS = {"northern": "n", "southern": "s", "eastern": "e", "western": "w", "middle": "m", "central": "c"}
_ORDINALS = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh"]
_SUFFIX = {1: "st", 2: "nd", 3: "rd"}

_PREFIXES = [
    r"united states (?:district )?court of appeals,? (?:for )?(?:the )?",
    r"u\.? ?s\.? (?:district )?court of appeals,? (?:for )?(?:the )?",
    r"court of appeals,? (?:for )?(?:the )?",
    r"united states district court,? (?:for )?(?:the )?",
    r"u\.? ?s\.? district court,? (?:for )?(?:the )?",
    r"district court of the united states,? (?:for )?(?:the )?",
    r"district court,? (?:for )?(?:the )?",
    r"united states court of appeals,? (?:for )?(?:the )?",
]


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _clean(text: str) -> str:
    t = text.strip()
    t = re.sub(r"\((?:en banc|per curiam|mem\.?|unpublished)[^)]*\)", " ", t, flags=re.IGNORECASE)
    t = t.strip("() \t")
    t = re.sub(r"[\s,]*\b(?:1[789]|20)\d{2}\)?\s*$", "", t)  # trailing "1997" of "(5th Cir. 1997)"
    return t.strip("() ,")


class CourtHierarchy:
    def __init__(self, courts: list[Court]):
        self._courts = {c.id: c for c in courts}
        self._alias: dict[str, str] = {}
        self._build_aliases()

    @classmethod
    def default(cls) -> CourtHierarchy:
        return _default_hierarchy()

    @classmethod
    def from_file(cls, path: Path) -> CourtHierarchy:
        return cls([Court(**c) for c in json.loads(Path(path).read_text())])

    def get(self, court_id: str) -> Court | None:
        return self._courts.get(court_id) if court_id else None

    def all(self) -> list[Court]:
        return list(self._courts.values())

    def circuit_of(self, court_id: str | None) -> str | None:
        c = self.get(court_id) if court_id else None
        return c.circuit if c else None

    def circuit_name(self, circuit: str | None) -> str | None:
        """'5' -> 'Fifth Circuit', 'dc' -> 'D.C. Circuit', 'fed' -> 'Federal Circuit'."""
        if not circuit:
            return None
        if circuit == "dc":
            return "D.C. Circuit"
        if circuit == "fed":
            return "Federal Circuit"
        return f"{_ORDINALS[int(circuit) - 1].capitalize()} Circuit"

    def districts_in(self, circuit: str) -> list[Court]:
        return [c for c in self._courts.values() if c.level == "district" and c.circuit == circuit]

    # ---- normalisation ----------------------------------------------------------------------------

    def _add(self, alias: str, court_id: str) -> None:
        k = _key(alias)
        if k:
            self._alias.setdefault(k, court_id)

    def _build_aliases(self) -> None:
        for c in self._courts.values():
            self._add(c.id, c.id)
            self._add(c.short_name, c.id)
            self._add(c.name, c.id)
            if c.level == "district" and c.state:
                state = STATE_NAMES.get(c.state, c.state).removeprefix("the ")
                m = re.search(r"for the (Northern|Southern|Eastern|Western|Middle|Central) District", c.name)
                div = m.group(1) if m else None
                abbr = f"{div[0]}.D." if div else "D."
                self._add(f"{abbr} {state}", c.id)  # "N.D. Texas"
                self._add(f"{abbr} {c.state}", c.id)  # "N.D. TX"
                self._add(f"District Court, {abbr} {state}", c.id)  # CourtListener style
                if div:
                    self._add(f"{div} District of {state}", c.id)
                else:
                    self._add(f"District of {state}", c.id)
                    self._add(f"{state} District", c.id)
            elif c.level == "appellate" and c.circuit:
                n = c.circuit
                if n.isdigit():
                    i = int(n)
                    suf = _SUFFIX.get(i, "th") if i not in (11, 12, 13) else "th"
                    for form in (f"{i}{suf}", f"{i}d", str(i), _ORDINALS[i - 1]):
                        for tail in ("Cir.", "Circuit", "Cir"):
                            self._add(f"{form} {tail}", c.id)
                    self._add(f"{_ORDINALS[i - 1]} circuit court of appeals", c.id)
                elif n == "dc":
                    for a in ("D.C. Cir.", "D.C. Circuit", "DC Circuit", "District of Columbia Circuit", "CADC"):
                        self._add(a, c.id)
                elif n == "fed":
                    for a in ("Fed. Cir.", "Federal Circuit", "CAFC"):
                        self._add(a, c.id)
        for a in ("District of Columbia", "D.D.C.", "District Court, D.C."):
            self._add(a, "dcd")
        for a in ("SCOTUS", "U.S.", "US Supreme Court", "United States Supreme Court", "Supreme Court",
                  "U.S. Supreme Court", "Supreme Court of the United States", "S. Ct.", "Supreme Court of the US"):
            self._add(a, "scotus")

    def normalize(self, text: str | None) -> str | None:
        """Map a Bluebook abbreviation, full name or loose phrase to a court id; None if unknown."""
        if not text or not text.strip():
            return None
        t = _clean(text)
        for cand in self._candidates(t):
            hit = self._alias.get(_key(cand))
            if hit:
                return hit
        return self._fallback(t.lower())

    @staticmethod
    def _candidates(t: str):
        yield t
        low = t
        for p in _PREFIXES:
            stripped = re.sub(f"^{p}", "", low, flags=re.IGNORECASE)
            if stripped != low:
                yield stripped
                yield re.sub(r"^(?:the )", "", stripped, flags=re.IGNORECASE)
        yield re.sub(r"^(?:the )", "", low, flags=re.IGNORECASE)

    def _fallback(self, t: str) -> str | None:
        t = t.replace("&", " and ")
        if re.search(r"\bsupreme court of the united states\b|\bu\.?s\.? supreme court\b", t):
            return "scotus"
        m = re.search(r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh)\s+circuit", t)
        if m and "district" not in t.replace("district of columbia circuit", ""):
            return f"ca{_ORDINALS.index(m.group(1)) + 1}"
        m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th|d)?\s+cir", t)
        if m and 1 <= int(m.group(1)) <= 11:
            return f"ca{int(m.group(1))}"
        if "district of columbia circuit" in t or "d.c. circuit" in t:
            return "cadc"
        if "federal circuit" in t:
            return "cafc"
        names = sorted(STATE_NAMES.items(), key=lambda kv: -len(kv[1]))
        for code, name in names:
            nm = name.removeprefix("the ").lower()
            m = re.search(rf"\b(northern|southern|eastern|western|middle|central)\s+district\s+of\s+{re.escape(nm)}\b", t)
            if m:
                return self._district(code, _DIVISIONS[m.group(1)])
        for code, name in names:
            nm = name.removeprefix("the ").lower()
            if re.search(rf"\bdistrict\s+of\s+{re.escape(nm)}\b", t):
                return self._district(code, None)
        return None

    def _district(self, state: str, div: str | None) -> str | None:
        for c in self._courts.values():
            if c.level == "district" and c.state == state:
                m = re.search(r"for the (Northern|Southern|Eastern|Western|Middle|Central) District", c.name)
                cdiv = _DIVISIONS[m.group(1).lower()] if m else None
                if cdiv == div:
                    return c.id
        return None


@lru_cache
def _default_hierarchy() -> CourtHierarchy:
    return CourtHierarchy.from_file(COURTS_JSON)


class AuthorityRanker:
    """Table 26 initial authority weights relative to the court of the matter."""

    def __init__(self, hierarchy: CourtHierarchy | None = None):
        self.h = hierarchy or CourtHierarchy.default()

    def rank(
        self,
        deciding_court_id: str | None,
        filing_court_id: str | None,
        *,
        published: bool = True,
        negative_treatment: bool = False,
    ) -> AuthorityRank:
        if negative_treatment:
            return AuthorityRank(status="flagged", weight=0.0, reason="Gate 4 warning: not used until reviewed")
        deciding = self.h.get(deciding_court_id) if deciding_court_id else None
        if deciding is None:
            return AuthorityRank(status="persuasive", weight=0.2, reason="Court not recognised; persuasive only")
        if deciding.level == "supreme":
            return AuthorityRank(status="binding", weight=1.0, reason="Supreme Court of the United States; binds every federal court")
        filing = self.h.get(filing_court_id) if filing_court_id else None
        fcirc = filing.circuit if filing else None
        same = fcirc is not None and deciding.circuit == fcirc
        pub = "published" if published else "unpublished"
        cname = self.h.circuit_name(deciding.circuit)
        if deciding.level == "appellate":
            if same:
                state = STATE_NAMES.get(filing.state or "") if filing and filing.state else None
                where = f"Court of appeals for {state} ({cname}), {pub}" if state else f"{cname}, {pub}"
                if published:
                    return AuthorityRank(status="binding", weight=0.9, reason=where)
                return AuthorityRank(status="persuasive", weight=0.6, reason=f"{where} (not binding)")
            return AuthorityRank(
                status="persuasive",
                weight=0.4 if published else 0.3,
                reason=f"Other circuit ({cname}), {pub}",
            )
        if same:
            return AuthorityRank(
                status="persuasive", weight=0.5, reason=f"District court within the {cname} ({deciding.short_name})"
            )
        return AuthorityRank(
            status="persuasive", weight=0.3, reason=f"District court outside the circuit ({deciding.short_name})"
        )
