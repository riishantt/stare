"""Case-record extraction from REDACTED complaint text.

Rule path (always available, used when `llm.is_offline`): court from the caption, parties, claims from
count headings / statute mentions, labelled key dates, posture and a short fact summary.
LLM path: `llm.complete_json` with a Pydantic schema; the result is validated (court id via the
hierarchy, theories / statutes / dates normalised) and gaps are filled from the rule path.
Falls back to rules on `LLMError`.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from stare.llm import ChatModel, LLMError, assert_redacted
from stare.schemas import CaseRecord, Claim, KeyDate, Party

log = logging.getLogger(__name__)

THEORIES = (
    "disparate_treatment", "retaliation", "hostile_work_environment", "failure_to_accommodate",
    "religious_accommodation", "pregnancy", "disparate_impact",
)
STATUTES = ("title_vii", "ada", "adea")

# ----------------------------------------------------------------------------------------------
# Court
# ----------------------------------------------------------------------------------------------

_DISTRICT_RE = re.compile(
    r"\b(?:Northern|Southern|Eastern|Western|Middle|Central)\s+District\s+of\s+(?:the\s+)?[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?", re.I)
_ABBREV_RE = re.compile(r"\b(?:[NSEWMC]\.\s?D\.|D\.)\s?(?:[A-Z][a-z]{0,5}\.?)(?:\s?[A-Z][a-z]{0,3}\.?)?")
_CIRCUIT_RE = re.compile(
    r"\b(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|Eleventh|D\.C\.|Federal)\s+Circuit\b", re.I)


def extract_court(text: str, hierarchy) -> tuple[str | None, str | None, str | None]:
    """Return (court_id, court_name, circuit) from the caption; (None, None, None) when unknown."""
    head = text[:2500]
    lines = [ln.strip() for ln in head.split("\n") if ln.strip()]
    cap_lines: list[str] = []
    for ln in lines[:14]:
        if re.search(r"\bv\.?s?\.?$|^Plaintiff|^Case\b|^Civil\b|^COMPLAINT", ln, re.I) and cap_lines:
            break
        if re.search(r"court|district|division|circuit|\bof\s+[A-Z]{3,}", ln, re.I):
            cap_lines.append(ln)
    candidates = [" ".join(cap_lines)] + cap_lines
    candidates += [m.group(0) for m in _DISTRICT_RE.finditer(head)]
    candidates += [m.group(0) for m in _ABBREV_RE.finditer(head)]
    candidates += [m.group(0) for m in _DISTRICT_RE.finditer(text)]
    candidates += [m.group(0) for m in _CIRCUIT_RE.finditer(text[:4000])]
    cid = None
    for cand in candidates:
        if not cand.strip():
            continue
        # a division line can follow the district: try "<district> <division>" pairs first
        cid = hierarchy.normalize(cand)
        if cid:
            break
    if not cid:
        return None, None, None
    court = hierarchy.get(cid)
    if not court:
        return None, None, None
    return court.id, court.name, court.circuit


# ----------------------------------------------------------------------------------------------
# Parties
# ----------------------------------------------------------------------------------------------

_UPPER_KEEP = {"LLC", "LLP", "LP", "USA", "US", "PLLC", "NA", "HR", "UPS", "IBM", "AT&T", "II", "III", "IV"}


def _pretty(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip(" ,;:\n\t")
    if not name or not name.isupper():
        return name
    out = []
    for w in name.split(" "):
        core = w.strip(".,")
        if core in _UPPER_KEEP:
            out.append(w)
        elif "-" in w:
            out.append("-".join(p.capitalize() for p in w.split("-")))
        else:
            out.append(w.capitalize())
    return " ".join(out)


def extract_parties(text: str) -> list[Party]:
    head = text[:3000]
    m_plain = re.search(r"(?im)^\s*(?:Plaintiffs?)\b[,.]?\s*$", head)
    parties: list[Party] = []
    # caption block: from the court header to the case number / COMPLAINT title
    end = re.search(r"(?im)^\s*(?:Civil Action|Case|C\.A\.|No\.)\b|^\s*[A-Z ,;:&-]*COMPLAINT\b", head)
    cap = head[: end.start()] if end else head[:1200]
    cap = re.sub(r"(?im)^.*\b(?:COURT|DISTRICT|DIVISION|CIRCUIT)\b.*$", "", cap)
    cap = cap.strip()
    pm = re.search(r"(?s)^(.*?)(?<![\[\w])(?:Plaintiffs?|PLAINTIFFS?)(?![\]\w])[,.]?", cap)
    if pm:
        name = re.sub(r"(?i),?\s*an individual\s*,?$", "", pm.group(1).strip().strip(",").strip())
        name = _clean_party(name)
        if name:
            parties.append(Party(role="plaintiff", name=name))
        rest = cap[pm.end():]
        dm = re.search(r"(?s)^\W*(?:\bv(?:s)?\b\.?)?(.*?)\b(?:Defendants?|DEFENDANTS?)\b", rest)
        if dm:
            dname = _clean_party(dm.group(1))
            if dname:
                parties.append(Party(role="defendant", name=_pretty(dname)))
    if not any(p.role == "plaintiff" for p in parties):
        m = re.search(r"Plaintiff\s+(\[(?:PLAINTIFF|PERSON_\d+)\])", text)
        if m:
            parties.append(Party(role="plaintiff", name=m.group(1)))
        elif m_plain or re.search(r"\bPlaintiff\b", head):
            parties.append(Party(role="plaintiff", name="[PLAINTIFF]"))
    if not any(p.role == "defendant" for p in parties):
        m = re.search(
            r"Defendants?\s+((?:[A-Z][\w&.'-]*,?\s+){1,5}(?:Inc\.?|LLC|L\.L\.C\.|Corp\.?|Corporation|Company|Co\.|Ltd\.?|LLP|L\.P\.|Group|Holdings))", text)
        if m:
            parties.append(Party(role="defendant", name=_pretty(m.group(1).rstrip(","))))
    return parties


def _clean_party(s: str) -> str:
    s = re.sub(r"(?im)^\s*(?:v\.?s?\.?)\s*$", "", s)
    s = re.sub(r"\s+", " ", s).strip(" ,;:")
    s = re.sub(r"^(?:v\.?s?\.?)\s+", "", s, flags=re.I)
    return s.strip(" ,;:")


# ----------------------------------------------------------------------------------------------
# Claims
# ----------------------------------------------------------------------------------------------

_COUNT_RE = re.compile(
    r"(?im)^\s*(?:(?:COUNT|CLAIM|CAUSE OF ACTION)\s+(?:[IVXLC|l1]+|\d+|ONE|TWO|THREE|FOUR|FIVE)(?!\w)|"
    r"(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH)\s+(?:CLAIM(?:\s+FOR\s+RELIEF)?|CAUSE\s+OF\s+ACTION))\s*[:.\-–—~_]*\s*(.*)$")
_SECTION_END = re.compile(r"(?im)^\s*(?:PRAYER|WHEREFORE|JURY DEMAND|DEMAND FOR JURY|RELIEF REQUESTED|REQUEST FOR RELIEF)\b")

_STATUTE_CUES = {
    "title_vii": re.compile(r"(?i)title\s+vii|2000e|civil rights act of 1964"),
    "ada": re.compile(r"(?i)americans with disabilities act|\bADAAA?\b|\b12(?:101|111|112|203)\b|disabilit"),
    "adea": re.compile(r"(?i)age discrimination in employment act|\bADEA\b|29 U\.S\.C\.\s*§+\s*(?:621|623|626)"),
}
_STATUTE_STRICT = {  # explicit statute mentions only (no generic words like "disability")
    "title_vii": _STATUTE_CUES["title_vii"],
    "ada": re.compile(r"(?i)americans with disabilities act|\bADAAA?\b|\b12(?:101|111|112|203)\b"),
    "adea": _STATUTE_CUES["adea"],
}


def _theory_of(s: str) -> str | None:
    t = s.lower()
    if "retaliat" in t:
        return "retaliation"
    if "hostile" in t:
        return "hostile_work_environment"
    if "religio" in t and "accommodat" in t:
        return "religious_accommodation"
    if "accommodat" in t:
        return "failure_to_accommodate"
    if "pregnan" in t:
        return "pregnancy"
    if "disparate impact" in t:
        return "disparate_impact"
    if re.search(r"disparate treatment|discriminat|wrongful|terminat|unlawful discharge|harass", t):
        return "disparate_treatment"
    return None


def _statute_of(s: str, theory: str | None) -> str | None:
    for st in ("ada", "adea", "title_vii"):
        if _STATUTE_STRICT[st].search(s):
            return st
    if theory in ("failure_to_accommodate",) and re.search(r"(?i)disabilit", s):
        return "ada"
    if re.search(r"(?i)\bage\b", s) and theory == "disparate_treatment":
        return "adea"
    if theory in ("pregnancy", "religious_accommodation", "hostile_work_environment"):
        return "title_vii"
    return None


def extract_claims(text: str) -> list[Claim]:
    doc_statutes = [st for st, pat in _STATUTE_STRICT.items() if pat.search(text)]
    if not doc_statutes:
        doc_statutes = [st for st, pat in _STATUTE_CUES.items() if pat.search(text)]
    claims: list[Claim] = []

    def add(statute: str | None, theory: str | None, desc: str) -> None:
        if not theory:
            return
        if statute is None:
            statute = doc_statutes[0] if len(doc_statutes) == 1 else _default_statute(theory, doc_statutes)
        if statute not in STATUTES:
            return
        if any(c.statute == statute and c.theory == theory for c in claims):
            return
        claims.append(Claim(statute=statute, theory=theory, description=desc))  # type: ignore[arg-type]

    matches = list(_COUNT_RE.finditer(text))
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        # a heading can wrap onto the next line
        after = text[m.end():m.end() + 160].lstrip("\n")
        nxt = after.split("\n", 1)[0].strip() if after else ""
        if nxt and not re.match(r"^\d+[.)]", nxt) and not heading.endswith(".") and len(nxt) < 100 and not nxt.isupper() \
                and not _COUNT_RE.match(nxt) and not _SECTION_END.match(nxt):
            heading = f"{heading} {nxt}".strip()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        pe = _SECTION_END.search(text, m.end(), end)
        body = text[m.end(): pe.start() if pe else end]
        theory = _theory_of(heading) or _theory_of(body[:400])
        statute = _statute_of(heading, theory) or _statute_of(body[:600], theory)
        add(statute, theory, re.sub(r"\s+", " ", heading)[:200])
    if claims:
        return claims

    # no count headings: infer from statute mentions and theory vocabulary across the document
    low = text
    for st in doc_statutes:
        found = False
        if re.search(r"(?i)retaliat", low):
            add(st, "retaliation", "Retaliation"); found = True
        if re.search(r"(?i)hostile work environment|harassment", low):
            add(st, "hostile_work_environment", "Hostile work environment"); found = True
        if st == "ada" and re.search(r"(?i)accommodat", low):
            add(st, "failure_to_accommodate", "Failure to accommodate"); found = True
        if st == "title_vii" and re.search(r"(?i)religio\w+\s+accommodat|accommodat\w+\s+(?:of|for)\s+(?:her|his|their)\s+religio", low):
            add(st, "religious_accommodation", "Religious accommodation"); found = True
        if st == "title_vii" and re.search(r"(?i)pregnan", low):
            add(st, "pregnancy", "Pregnancy discrimination"); found = True
        if re.search(r"(?i)disparate impact", low):
            add(st, "disparate_impact", "Disparate impact"); found = True
        if re.search(r"(?i)discriminat|terminat|fired|demot", low) or not found:
            add(st, "disparate_treatment", "Discrimination (disparate treatment)")
    return claims


def _default_statute(theory: str, doc_statutes: list[str]) -> str | None:
    if theory == "failure_to_accommodate" and "ada" in doc_statutes:
        return "ada"
    if theory in ("religious_accommodation", "pregnancy") and "title_vii" in doc_statutes:
        return "title_vii"
    if doc_statutes:
        return doc_statutes[0]
    return {"failure_to_accommodate": "ada"}.get(theory, "title_vii")


# ----------------------------------------------------------------------------------------------
# Dates
# ----------------------------------------------------------------------------------------------

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_MON = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
_DATE_RE = re.compile(
    rf"(?P<mdy>\b{_MON}\.?\s+(?P<d1>\d{{1,2}})(?:st|nd|rd|th)?,?\s+(?P<y1>\d{{4}}))"
    rf"|(?P<dmy>\b(?P<d2>\d{{1,2}})\s+{_MON}\.?,?\s+(?P<y2>\d{{4}}))"
    rf"|(?P<num>(?<![\d/.-])(?P<m3>\d{{1,2}})/(?P<d3>\d{{1,2}})/(?P<y3>\d{{4}}|\d{{2}})(?![\d/]))"
    rf"|(?P<iso>(?<![\d-])(?P<y4>\d{{4}})-(?P<m4>\d{{2}})-(?P<d4>\d{{2}})(?![\d-]))"
    rf"|(?P<my>\b{_MON}\.?,?\s+(?P<y5>\d{{4}}))",
    re.I,
)


def _month_of(token: str) -> int:
    m = re.match(rf"{_MON}", token, re.I)
    return _MONTHS[m.group(0)[:3].lower()] if m else 0


def normalize_date(s: str) -> str | None:
    """'March 3, 2026' / '03/03/2026' / '3 March 2026' -> '2026-03-03'; 'March 2026' -> '2026-03'."""
    m = _DATE_RE.fullmatch(s.strip())
    return _iso(m) if m else None


def _iso(m: re.Match[str]) -> str | None:
    try:
        if m.group("mdy"):
            y, mo, d = int(m.group("y1")), _month_of(m.group("mdy")), int(m.group("d1"))
        elif m.group("dmy"):
            y, mo, d = int(m.group("y2")), _month_of(m.group("dmy").split(None, 1)[1]), int(m.group("d2"))
        elif m.group("num"):
            y = int(m.group("y3"))
            y = y + 2000 if y < 100 else y
            mo, d = int(m.group("m3")), int(m.group("d3"))
        elif m.group("iso"):
            y, mo, d = int(m.group("y4")), int(m.group("m4")), int(m.group("d4"))
        else:
            y, mo = int(m.group("y5")), _month_of(m.group("my"))
            if not 1 <= mo <= 12 or not 1900 <= y <= 2100:
                return None
            return f"{y:04d}-{mo:02d}"
        return date(y, mo, d).isoformat()
    except (ValueError, KeyError):
        return None


_DATE_LABELS: list[tuple[str, re.Pattern[str]]] = [
    ("Right-to-sue letter", re.compile(r"(?i)right[\s-]+to[\s-]+sue")),
    ("EEOC charge filed", re.compile(r"(?i)charge of discrimination|\bcharge\b(?:\s+(?:no\.?\s*\S+\s+)?with)|filed\s+(?:a|an|her|his|their)?\s*(?:timely\s+|formal\s+)?(?:EEOC\s+)?charge|EEOC\s+charge")),
    ("Termination", re.compile(r"(?i)terminat\w*|fired|discharged|dismissed from|laid off|let go|separation|separated")),
    ("Hire", re.compile(r"(?i)\bhired\b|began (?:her |his |their )?employment|started (?:work|working)|joined (?:the )?(?:company|acme)|commenced employment")),
    ("Accommodation request", re.compile(r"(?i)request(?:ed|s)?[^.]{0,80}accommodat|accommodation request|asked[^.]{0,120}accommodat|asked\s+(?:her|his|their)\s+(?:supervisor|manager)")),
    ("Protected complaint", re.compile(r"(?i)complain\w*|reported\b|protected activity|grievance|opposed|raised concerns?|objected")),
    ("Complaint filed", re.compile(r"(?i)\bDated\b|files? this (?:complaint|action)|date filed|\bfiled this\b")),
]


def extract_key_dates(text: str) -> list[KeyDate]:
    spans: list[tuple[int, int, str]] = []
    for m in _DATE_RE.finditer(text):
        iso = _iso(m)
        if iso:
            spans.append((m.start(), m.end(), iso))
    found: dict[str, str] = {}
    prev_end = 0
    for i, (s, e, iso) in enumerate(spans):
        # clause = text since the previous sentence end / previous date, up to this date
        sent_start = max(text.rfind(". ", 0, s), text.rfind(".\n", 0, s), text.rfind("\n\n", 0, s), 0)
        start = max(sent_start, spans[i - 1][1] if i else 0, s - 220)
        before = text[start:s]
        best: tuple[int, str] | None = None
        for label, pat in _DATE_LABELS:
            for m in pat.finditer(before):
                if best is None or m.end() > best[0]:
                    best = (m.end(), label)
        if best is None:
            nxt = spans[i + 1][0] if i + 1 < len(spans) else len(text)
            after = text[e:min(nxt, e + 70)].split(".")[0]
            for label, pat in _DATE_LABELS:
                m = pat.search(after)
                if m and (best is None or m.start() < best[0]):
                    best = (m.start(), label)
        if best and best[1] not in found:
            found[best[1]] = iso
    return sorted((KeyDate(label=k, date=v) for k, v in found.items()), key=lambda k: (k.date, k.label))


# ----------------------------------------------------------------------------------------------
# Posture and facts
# ----------------------------------------------------------------------------------------------


def extract_posture(text: str) -> str:
    low = text.lower()
    if re.search(r"motion for summary judgment", low):
        return "Summary judgment motion pending"
    if re.search(r"motion to dismiss|rule 12\(b\)", low):
        return "Motion to dismiss pending"
    if re.search(r"\banswer\b[^.]{0,30}\bfiled\b|defendant'?s answer", low):
        return "Complaint filed; answer filed"
    if re.search(r"\bcomplaint\b", low[:3000]) or "jury demand" in low:
        return "Complaint filed; no answer yet"
    if re.search(r"charge of discrimination|\beeoc\b", low):
        return "Pre-suit; administrative (EEOC) stage"
    return ""


_FACT_HEAD = re.compile(r"(?im)^\s*(?:STATEMENT OF )?(?:FACTUAL ALLEGATIONS|FACTS|FACTUAL BACKGROUND|STATEMENT OF FACTS|BACKGROUND)\s*$")
_PARA_START = re.compile(r"(?m)^\s*(\d{1,3})[.)]\s+(?=\S)")


def _paragraphs(block: str) -> list[str]:
    starts = list(_PARA_START.finditer(block))
    paras = []
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(block)
        chunk = block[m.end():end]
        # stop at an all-caps heading line
        lines = []
        for ln in chunk.split("\n"):
            if ln.strip() and ln.strip() == ln.strip().upper() and len(ln.strip()) > 6 and re.search(r"[A-Z]{4}", ln) \
                    and not re.search(r"\[[A-Z_0-9]+\]", ln):
                break
            lines.append(ln.strip())
        para = re.sub(r"\s+", " ", " ".join(lines)).strip()
        if para:
            paras.append(para)
    return paras


def extract_facts(text: str, limit: int = 1200, n: int = 5) -> str:
    paras: list[str] = []
    h = _FACT_HEAD.search(text)
    if h:
        end = _COUNT_RE.search(text, h.end())
        paras = _paragraphs(text[h.end(): end.start() if end else len(text)])
    if not paras:
        body = text
        skip = re.compile(r"(?i)jurisdiction|venue|\bis proper\b|incorporates|this is an action|exhaust|right to sue|\bparties\b")
        paras = [p for p in _paragraphs(body) if not skip.search(p[:200])]
    if not paras:  # unnumbered prose
        paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 80]
    out = ""
    for p in paras[:n]:
        nxt = f"{out} {p}".strip()
        if len(nxt) > limit:
            room = limit - len(out) - 1
            if room > 80:
                out = f"{out} {p[:room].rsplit(' ', 1)[0]}...".strip()
            break
        out = nxt
    return out[:limit]


def count_placeholders(text: str) -> int:
    return len(re.findall(r"\[[A-Z][A-Z_]*(?:_\d+)?\]", text))


# ----------------------------------------------------------------------------------------------
# Rule path / LLM path
# ----------------------------------------------------------------------------------------------


def extract_case_record_rules(redacted_text: str, hierarchy) -> CaseRecord:
    cid, cname, circuit = extract_court(redacted_text, hierarchy)
    return CaseRecord(
        court_id=cid,
        court_name=cname,
        circuit=circuit,
        parties=extract_parties(redacted_text),
        claims=extract_claims(redacted_text),
        key_dates=extract_key_dates(redacted_text),
        procedural_posture=extract_posture(redacted_text),
        facts_summary=extract_facts(redacted_text),
        redaction_count=count_placeholders(redacted_text),
        client_side="plaintiff",
    )


class _LLMParty(BaseModel):
    role: Literal["plaintiff", "defendant", "other"]
    name: str


class _LLMClaim(BaseModel):
    statute: str = Field(description="one of: title_vii, ada, adea")
    theory: str = Field(description="one of: " + ", ".join(THEORIES))
    description: str = ""


class _LLMDate(BaseModel):
    label: str
    date: str = Field(description="ISO date YYYY-MM-DD, or YYYY-MM when only the month is known")


class LLMCaseExtraction(BaseModel):
    court_name: str | None = Field(default=None, description="court named in the caption")
    court_id: str | None = Field(default=None, description="CourtListener id such as txnd, cand, ca5; null if unsure")
    parties: list[_LLMParty] = Field(default_factory=list)
    claims: list[_LLMClaim] = Field(default_factory=list)
    key_dates: list[_LLMDate] = Field(default_factory=list)
    procedural_posture: str = ""
    facts_summary: str = Field(default="", description="at most 1200 characters")


_LLM_SYSTEM = (
    "You extract structured facts from a REDACTED US federal employment-discrimination complaint "
    "(Title VII, ADA, ADEA). Placeholders such as [PLAINTIFF] and [PERSON_1] stand for individuals: keep them "
    "verbatim and never guess the real names. Use only what the text states. Return JSON matching the schema. "
    "Allowed statutes: title_vii, ada, adea. Allowed theories: " + ", ".join(THEORIES) + ". "
    "Dates must be ISO (YYYY-MM-DD, or YYYY-MM if only the month is known)."
)


def _llm_record(redacted_text: str, llm: ChatModel, hierarchy) -> CaseRecord:
    prompt = "Complaint text:\n\n" + redacted_text[:14000]
    assert_redacted(prompt)
    raw = llm.complete_json(_LLM_SYSTEM, prompt, LLMCaseExtraction, tier="main", max_tokens=2500)
    rules = extract_case_record_rules(redacted_text, hierarchy)

    cid = None
    if raw.court_id and hierarchy.get(raw.court_id):
        cid = raw.court_id
    if not cid:
        cid = hierarchy.normalize(raw.court_id) or hierarchy.normalize(raw.court_name)
    court = hierarchy.get(cid) if cid else None
    if not court:
        cid, court = rules.court_id, (hierarchy.get(rules.court_id) if rules.court_id else None)

    claims: list[Claim] = []
    for c in raw.claims:
        theory = c.theory if c.theory in THEORIES else _theory_of(c.theory) or _theory_of(c.description)
        statute = c.statute if c.statute in STATUTES else _statute_of(c.statute + " " + c.description, theory)
        if theory and statute and not any(x.statute == statute and x.theory == theory for x in claims):
            claims.append(Claim(statute=statute, theory=theory, description=c.description[:200]))  # type: ignore[arg-type]

    dates: list[KeyDate] = []
    for d in raw.key_dates:
        iso = d.date if re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", d.date) else normalize_date(d.date)
        if iso and d.label.strip():
            dates.append(KeyDate(label=d.label.strip(), date=iso))

    parties = [Party(role=p.role, name=p.name.strip()) for p in raw.parties if p.name.strip()]
    return CaseRecord(
        court_id=court.id if court else None,
        court_name=court.name if court else (raw.court_name or None),
        circuit=court.circuit if court else None,
        parties=parties or rules.parties,
        claims=claims or rules.claims,
        key_dates=dates or rules.key_dates,
        procedural_posture=raw.procedural_posture.strip() or rules.procedural_posture,
        facts_summary=(raw.facts_summary.strip() or rules.facts_summary)[:1200],
        redaction_count=count_placeholders(redacted_text),
        client_side="plaintiff",
    )


def extract_case_record(redacted_text: str, llm: ChatModel, hierarchy) -> CaseRecord:
    if not getattr(llm, "is_offline", True):
        try:
            return _llm_record(redacted_text, llm, hierarchy)
        except LLMError as exc:
            log.warning("LLM case extraction failed (%s); using the rule-based extractor", type(exc).__name__)
        except ValueError as exc:  # pydantic validation of a malformed model reply
            log.warning("LLM case extraction returned invalid JSON (%s); using rules", type(exc).__name__)
    return extract_case_record_rules(redacted_text, hierarchy)
