"""Negative-treatment detection for Gate 4: phrases, proximity rules and name/cite mention finding."""

from __future__ import annotations

import re
from dataclasses import dataclass

from stare.citations.reporters import _tokens, split_case_name

WINDOW = 300
WEAK_WINDOW = 110

# (label, regex, strong). Strong phrases count anywhere in the +/-300 char window around a mention
# of the case; weak ones (reversed/vacated) only in the same sentence right after the mention.
_PHRASES: list[tuple[str, re.Pattern[str], bool]] = [
    ("overruled", re.compile(r"\b(?:overruled|overruling|overrules|overrule)\b", re.IGNORECASE), True),
    ("abrogated", re.compile(r"\b(?:abrogated|abrogating|abrogates)\b", re.IGNORECASE), True),
    ("superseded by statute", re.compile(
        r"\b(?:superseded|supplanted|legislatively\s+(?:overruled|overturned|superseded)|displaced)\s+by\s+(?:the\s+)?(?:statute|legislation|congress|act|amendments?|\d)|"
        r"\bsuperseded\s+by\s+statute|\bsuperseded\s+by\b[^.]{0,60}\b(?:Act|Amendments)\b|"
        r"\bstatutorily\s+(?:overruled|superseded)|\bcongress\b[^.]{0,40}\b(?:overrode|overruled|rejected)\b", re.IGNORECASE), True),
    ("disapproved", re.compile(r"\b(?:disapproved|disapproving)\b", re.IGNORECASE), True),
    ("no longer good law", re.compile(r"\bno\s+longer\s+(?:good\s+law|controlling|valid|binding|viable)\b|\bnot\s+good\s+law\b", re.IGNORECASE), True),
    ("called into doubt", re.compile(r"\b(?:called|calls|calling|cast|casts)\s+(?:\w+\s+)?into\s+(?:serious\s+)?(?:doubt|question)\b", re.IGNORECASE), True),
    ("reversed", re.compile(r"\b(?:rev'd|reversed|vacated)\b", re.IGNORECASE), False),
]
_NEGATION = re.compile(r"\b(?:not|never|nor|n't|declin\w+|refus\w+|without|neither|no\s+court|hasn't|hasn’t|didn’t|didn't|doesn’t|doesn't)\s+(?:\w+\s+){0,3}$", re.IGNORECASE)
_OTHER_CITE = re.compile(r"\b\d{1,4}\s+(?:U\.S\.|S\.\s?Ct\.|F\.\s?(?:2d|3d|4th)|F\.\s?Supp\.(?:\s?[23]d)?|L\.\s?Ed\.(?:\s?2d)?|F\.\s?App'x)\s+\d+")
_AGENT_BY = re.compile(
    r"(?:\s*,?\s*(?:in\s+part|on\s+other\s+grounds|in\s+relevant\s+part|as\s+recognized|implicitly|partially|sub\s+silentio))*\s*,?\s*by\b",
    re.IGNORECASE,
)
# Between a citation and a weak phrase in subsequent-history position: "X, 1 U.S. 2 (1990), rev'd" or
# "X, 1 U.S. 2, was later vacated". Anything else ("In X, the Court reversed the Sixth Circuit") is X acting.
_HISTORY_GAP = re.compile(
    r"[\s,]*(?:at\s+)?\*?[\d\s,–-]*(?:\([^()]*\)[\s,]*)*"
    r"(?:(?:aff'd|affirmed)\s+in\s+part[\s,]*(?:and\s+)?|(?:which\s+)?(?:was|were|is|has\s+been|had\s+been)\s+(?:later\s+|subsequently\s+)?)?",
    re.IGNORECASE,
)
_ACTIVE_OBJECT = re.compile(r"\s+(?:in\s+part\s+)?(?:the\s+)?(?:[A-Z]|\d)")
_GENERIC_FIRST = {"united", "state", "states", "people", "city", "county", "commonwealth", "matter", "estate", "board", "doe", "smith"}


@dataclass
class Finding:
    label: str
    snippet: str

    def __str__(self) -> str:
        return f"{self.label}: “{self.snippet}”"


def mention_patterns(case_name: str, cites: list[str]) -> list[re.Pattern[str]]:
    """Regexes that identify a mention of this case in a citing opinion: its reporter cites
    (full and short form) and its name (full name, first party, first distinctive word)."""
    pats: list[str] = []
    for c in cites:
        m = re.match(r"\s*(\d+)\s+(.+?)\s+(\d[\w\-]*)\s*$", c or "")
        if m:
            vol, rep, page = m.groups()
            rep_re = r"\s*".join(re.escape(ch) for ch in rep.replace(" ", ""))
            pats.append(rf"\b{vol}\s*{rep_re}\s*(?:at\s+)?\*?{re.escape(page)}\b")
            pats.append(rf"\b{vol}\s*{rep_re}\s+at\s+\d+")
    sides = split_case_name(case_name)
    if case_name:
        pats.append(re.escape(case_name.strip()).replace(r"\ ", r"\s+"))
    if sides:
        first = sides[0]
        if len(first) >= 5:
            pats.append(re.escape(first.strip(" ,.")).replace(r"\ ", r"\s+"))
        toks = _tokens(first)
        if toks and toks[0] not in _GENERIC_FIRST and len(toks[0]) >= 5:
            pats.append(rf"\b{re.escape(toks[0])}\b")
    return [re.compile(p, re.IGNORECASE) for p in dict.fromkeys(pats)]


def _sentence_end(text: str, pos: int) -> int:
    m = re.compile(r"[.!?](?=\s+[A-Z])").search(text, pos)
    return m.end() if m else len(text)


def scan_context(text: str, patterns: list[re.Pattern[str]], *, require_mention: bool = True, limit: int = 3) -> list[Finding]:
    """Negative-treatment phrases attributable to the case that `patterns` identify."""
    if not text:
        return []
    findings: list[Finding] = []
    seen: set[str] = set()
    mentions: list[tuple[int, int]] = []
    for p in patterns:
        mentions += [m.span() for m in p.finditer(text)]
    if not require_mention:
        mentions = [(len(text) // 2, len(text) // 2)]
    mentions.sort()
    for ms, me in mentions:
        lo, hi = max(0, ms - WINDOW), min(len(text), me + WINDOW)
        window = text[lo:hi]
        for label, rx, strong in _PHRASES:
            for pm in rx.finditer(window):
                ps, pe = lo + pm.start(), lo + pm.end()
                if ms <= ps < me or ms < pe <= me:
                    continue
                if _NEGATION.search(text[max(0, ps - 45):ps]):
                    continue
                before = ps < ms
                after_phrase = _AGENT_BY.match(text, pe)
                if after_phrase and any(0 <= s - after_phrase.end() < 25 for s, _ in mentions):
                    continue  # "overruled (on other grounds) by <this case>": this case is the overruler
                if (not before and label in ("overruled", "abrogated", "disapproved")
                        and _ACTIVE_OBJECT.match(text, pe) and not _AGENT_BY.match(text, pe)):
                    continue  # "<this case> overruled Smith v. Jones": active voice, this case is the overruler
                if label == "overruled" and re.search(r"\bobjection\b|\bmotion\b", text[max(0, ps - 70):pe + 12], re.IGNORECASE):
                    continue
                if require_mention:
                    # The phrase must be about this case: right after its citation in the same sentence
                    # ("Mattern, 104 F.3d at 707, abrogated by ...") or directly before its name ("overruling Mattern").
                    if before and (ms - pe > 40 or _sentence_end(text, ps) < ms):
                        continue
                    if not before and (ps - me > (120 if strong else WEAK_WINDOW) or ps > _sentence_end(text, me)):
                        continue
                    if before and not strong:
                        continue
                    if not before and not strong and not _HISTORY_GAP.fullmatch(text[me:ps]):
                        continue
                elif not strong:
                    continue
                if require_mention:
                    between = text[min(me, ps):max(ms, pe)] if not before else text[pe:ms]
                    if _OTHER_CITE.search(between):
                        continue  # another case is cited in between: the phrase is about that one
                s0 = max(0, min(ps, ms) - 60)
                s0 = text.rfind(" ", 0, s0) + 1 if s0 else 0
                s1 = text.find(" ", min(len(text), max(pe, me) + 60))
                snippet = re.sub(r"\s+", " ", text[s0:s1 if s1 != -1 else len(text)]).strip()
                key = f"{label}:{ps // 200}"
                if key in seen:
                    continue
                seen.add(key)
                findings.append(Finding(label, snippet))
                if len(findings) >= limit:
                    return findings
    return findings


def has_authority_over(citing_court: str | None, cited_court: str | None, hierarchy) -> bool:
    """Only a court with authority over a precedent can overrule or abrogate it: the Supreme Court over
    everything; a court of appeals over its own circuit's decisions (en banc or an intervening panel
    rule) and its district courts. Unknown courts are given the benefit of the doubt (warn, don't miss)."""
    citing = hierarchy.get(citing_court) if citing_court else None
    cited = hierarchy.get(cited_court) if cited_court else None
    if citing is None or cited is None:
        return True
    if citing.level == "supreme":
        return True
    if cited.level == "supreme":
        return False
    if citing.level == "appellate":
        return cited.circuit == citing.circuit and cited.level in ("appellate", "district", "bankruptcy")
    return False
