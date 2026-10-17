"""PII redaction (NFR-03): nothing leaves Intake un-redacted.

Two layers:
* a regex layer that always runs (SSN, e-mail, phone, DOB, street address, ZIP+4, ID / account /
  card / licence numbers, plus cue-based and gazetteer-based person names);
* an optional Presidio layer (spaCy ``en_core_web_sm``, loaded lazily once) that adds PERSON and
  residence LOCATION entities.

Legal vocabulary (courts, agencies, statutes, judges, reported case names, company defendants) is
protected: a person/location candidate overlapping a protected span is never redacted.
Individuals are redacted, organisations are not. Raw text is never logged.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Literal

from stare.schemas import RedactedEntity, RedactionResult

log = logging.getLogger(__name__)

# ----------------------------------------------------------------------------------------------
# Vocabulary
# ----------------------------------------------------------------------------------------------

_TITLES = r"(?:Mr|Mrs|Ms|Miss|Mx|Dr)"
_TOK = r"(?:[A-Z][a-z]+(?:[-'’][A-Z]?[a-z]+)*|Mc[A-Z][a-z]+|O'[A-Z][a-z]+)"
_FULL = rf"{_TOK}(?:[ \t]+(?:[A-Z]\.|{_TOK})){{1,3}}"
_FULLU = r"(?:[A-Z][A-Za-z'’-]+|[A-Z]\.)(?:[ \t]+(?:[A-Z]\.|[A-Z][A-Za-z'’-]+)){1,3}"  # also ALL-CAPS
_NAME = rf"(?:{_FULL}|{_TOK})"

_FIRST_NAMES = """
james john robert michael william david richard joseph thomas charles christopher daniel matthew anthony mark donald
steven paul andrew joshua kenneth kevin brian george timothy ronald edward jason jeffrey ryan jacob gary nicholas
eric jonathan stephen larry justin scott brandon benjamin samuel gregory frank alexander raymond patrick jack dennis
jerry tyler aaron jose adam nathan henry douglas zachary peter kyle walter ethan jeremy harold keith christian roger
noah gerald carl terry sean austin arthur lawrence jesse dylan bryan joe jordan billy bruce albert willie gabriel
logan alan juan wayne roy ralph randy eugene vincent russell elijah louis bobby philip johnny marcus derek omar
mary patricia jennifer linda elizabeth barbara susan jessica sarah karen nancy lisa betty margaret sandra ashley
kimberly emily donna michelle dorothy carol amanda melissa deborah stephanie rebecca sharon laura cynthia kathleen
amy angela shirley anna brenda pamela emma nicole helen samantha katherine christine debra rachel carolyn janet
catherine maria heather diane ruth julie olivia joyce virginia victoria kelly lauren christina joan evelyn judith
megan andrea cheryl hannah jacqueline martha gloria teresa ann sara madison frances kathryn janice jean abigail
alice julia judy sophia grace denise amber doris marilyn danielle beverly isabella theresa diana natalie brittany
charlotte marie kayla alexis lori priya aisha fatima carlos luis miguel jorge ahmed mohammed ali hassan raj amit
wei li chen ming jin yuki hiroshi ivan olga natasha dmitri tomas elena rosa carmen lucia pedro diego sofia
denise darnell latoya tamika jamal tyrone shanice keisha deshawn
""".split()
_FIRST_RE = "|".join(sorted({n.capitalize() for n in _FIRST_NAMES}, key=len, reverse=True))

_ROLE_CUES = (
    r"supervisor|manager|co-?worker|colleague|director|recruiter|nurse|employee|foreman|boss|vice president|"
    r"president|CEO|CFO|COO|HR (?:representative|manager|director|partner)|human resources (?:manager|director|representative)|"
    r"investigator|physician|doctor|therapist|named|called|told|asked|emailed|e-mailed|texted|reported to|"
    r"spoke with|spoke to|met with|fired by|terminated by|supervised by|managed by|hired by|interviewed by|"
    r"complained to|reported (?:it |this )?to|attorney|counsel|witness|declarant"
)

_STOP_TOKENS = {
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for", "by", "with", "from", "was", "is", "were",
    "are", "has", "had", "have", "that", "this", "these", "those", "his", "her", "their", "its", "it", "he", "she",
    "they", "who", "whom", "which", "when", "where", "while", "after", "before", "during", "plaintiff", "defendant",
    "plaintiffs", "defendants", "count", "complaint", "court", "county", "state", "united", "states", "america",
    "title", "vii", "act", "section", "paragraph", "exhibit", "company", "inc", "llc", "corp", "corporation", "ltd",
    "employment", "opportunity", "commission", "equal", "district", "division", "northern", "southern", "eastern",
    "western", "middle", "central", "circuit", "department", "human", "resources", "supervisor", "manager",
    "director", "warehouse", "jury", "trial", "demand", "relief", "prayer", "wherefore", "respectfully", "submitted",
    "dated", "date", "civil", "action", "case", "no", "number", "federal", "rules", "procedure", "right", "sue",
    "notice", "charge", "discrimination", "retaliation", "disability", "accommodation", "age", "race", "religion",
    "sex", "national", "origin", "hostile", "work", "environment", "disparate", "treatment", "impact", "monday",
    "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "january", "february", "march", "april",
    "may", "june", "july", "august", "september", "october", "november", "december", "parties", "party", "claim",
    "claims", "facts", "factual", "allegations", "jurisdiction", "venue", "background", "introduction", "nature",
    "attorney", "attorneys", "counsel", "esq", "pro", "se", "hon", "honorable", "judge", "justice", "magistrate",
    "not", "no", "yes", "all", "any", "each", "such", "upon", "within", "without", "also", "then", "than", "because",
    "however", "therefore", "thus", "here", "there", "as", "if", "but", "so", "i", "we", "you", "our", "my", "me",
    "mr", "mrs", "ms", "miss", "dr", "sr", "jr", "ii", "iii", "iv", "texas", "california", "new", "york", "illinois",
    "dallas", "fort", "worth", "san", "francisco", "oakland", "chicago", "street", "avenue", "road",
}

_KNOWN_CASE_NAMES = [
    "McDonnell Douglas", "Burlington Northern", "Burlington Industries", "Faragher", "Ellerth", "Griggs",
    "Nassar", "Staub", "Muldrow", "Bostock", "Groff", "Reeves v. Sanderson", "Swierkiewicz", "Hishon",
    "Harris v. Forklift", "Meritor", "Oncale", "Vance v. Ball State", "Young v. United Parcel Service",
    "Texas Department of Community Affairs v. Burdine", "St. Mary's Honor Center", "Hicks", "Desert Palace",
    "Price Waterhouse", "Gross v. FBL", "Smith v. City of Jackson", "Wards Cove", "Toyota Motor Manufacturing",
    "US Airways v. Barnett", "Sutton v. United Air Lines", "Thompson v. North American Stainless",
    "Crawford v. Metropolitan Government", "Kasten", "Ames v. Ohio", "EEOC v. Abercrombie", "Abercrombie",
    "Trans World Airlines v. Hardison", "Hardison", "Ricci v. DeStefano", "Hazen Paper", "O'Connor v. Consolidated",
    "Hubbard", "Lujan",
]

_JUDGE_CUE = r"(?:(?:Chief|Senior|Magistrate|District|Circuit|Associate)\s+)*(?:Judge|Justice|Hon\.|Honorable|Chancellor)"

_ORG_SUFFIX = (
    r"(?:Inc\.?|INC\.?|LLC|L\.L\.C\.|Corp\.?|CORP\.?|Corporation|CORPORATION|Co\.|Company|COMPANY|Ltd\.?|LTD\.?|LLP|L\.P\.|LP|"
    r"PLLC|P\.C\.|Holdings|Group|Associates|Partners|Enterprises|Industries|Logistics|Services|Systems|Solutions|"
    r"Hospital|University|Bank|Foundation|Stores|Airlines|Technologies|Manufacturing)"
)

_CAPTION_WORD = r"(?:[A-Z(\[]\S*|of|for|the|and|in|at|de|[-–—:,&])"

_PROTECT_PATTERNS: list[re.Pattern[str]] = [
    # courts
    # caption lines ("IN THE UNITED STATES DISTRICT COURT", title-cased by _analysis_text) in which every word is
    # capitalised. Never a whole prose line, which may name a person ("Plaintiff told the court that Karen Miller").
    re.compile(r"(?m)^[ \t]*(?=[^\n]*\b(?:Court|Circuit|Division)\b)" + _CAPTION_WORD + r"(?:[ \t]+" + _CAPTION_WORD + r")*[ \t]*$"),
    re.compile(r"\b(?:Northern|Southern|Eastern|Western|Middle|Central)\s+District\s+of\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?"),
    re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+Division\b"),
    re.compile(r"\b(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|Eleventh|D\.C\.|Federal)\s+Circuit\b"),
    re.compile(r"\b(?:United States|U\.S\.)\s+(?:District\s+|Bankruptcy\s+)?Court(?:\s+of\s+Appeals)?(?:\s+(?:for|of)\s+the\s+[A-Z][\w.]*(?:\s+(?:Circuit|District)(?:\s+of\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?)?)?"),
    re.compile(r"\b(?:U\.S\.|United States)\s+Supreme\s+Court\b|\bSupreme Court\b"),
    # agencies / generic institutions
    re.compile(r"\bEqual Employment Opportunity Commission\b|\bEEOC\b"),
    # not a job title that follows a name ("Linda Brown Office Manager", "Tom Lee Department Head")
    re.compile(r"\b(?:[A-Z][a-z]+\s+){1,4}(?:Commission|Department|Agency|Bureau|Administration|Board|Office|Council|Committee)\b"
               r"(?!\s+(?:Manager|Head|Member|Assistant|Supervisor|Director|Coordinator|Administrator|Chair|Clerk|Lead)\b)"),
    # statutes, rules, regulations
    re.compile(r"\b(?:[A-Z][a-z]+\s+){0,6}(?:of\s+(?:the\s+)?)?(?:[A-Z][a-z]+\s+){0,3}Act(?:\s+of\s+\d{4})?\b"),
    re.compile(r"\bTitle\s+(?:VII|I|II|III|IX)\b"),
    # cited cases ("Martinez v. Delta Air Lines, Inc., 2019 WL 4639462"): a caption followed by a reporter cite
    re.compile(r"\b[A-Z][\w.'’&-]*(?:\s+(?:[A-Z][\w.'’&-]*|of|the|and|ex\s+rel\.|&))*\s+v\.\s+[A-Z][\w.'’&-]*"
               r"(?:,?\s+(?:[A-Z][\w.'’&-]*|of|the|and|&))*(?=,\s+(?:\d{1,4}\s+[A-Z]|\d{4}\s+(?:WL|U\.S\. Dist\.)|\d{4}\s+[A-Z]{2}\s+App))"),
    re.compile(r"\b\d+\s+(?:U\.S\.C\.|C\.F\.R\.)[^,;\n]*"),
    re.compile(r"\bFed(?:eral|\.)\s+R(?:ules|\.)\s+(?:of\s+)?Civ(?:il|\.)\s+P(?:rocedure|\.)[^,;\n]*"),
    re.compile(r"\bADEA\b|\bADA\b|\bADAAA\b"),
    # reported case names: "X v. Y, 411 U.S. 792"
    re.compile(
        r"\b[A-Z][\w.'&-]*(?:\s+(?:[A-Z][\w.'&-]*|of|the|and|&|de|for|v\.)){0,5}?\s+v\.\s+"
        r"[A-Z][\w.'&-]*(?:\s+(?:[A-Z][\w.'&-]*|of|the|and|&|de|for)){0,6}?(?=,?\s+\d+\s+[A-Z])"
    ),
    # organisations (company defendants)
    re.compile(rf"\b(?:(?!Plaintiff|Defendant)[A-Z][\w&.'-]*[ \t]+){{1,5}}{_ORG_SUFFIX}(?=\W|$)"),
    re.compile(rf"\b(?:(?!Plaintiff|Defendant)[A-Z][\w&.'-]*,?[ \t]+){{1,5}}{_ORG_SUFFIX}(?=\W|$)"),
    # case-sensitive: with re.I "Smith and a co-worker" would read as a company and protect "Smith"
    re.compile(r"\b(?:(?!Plaintiff|Defendant)[A-Z][\w&.'-]*[ \t]+){1,4}(?:Inc|INC|LLC|Corp|CORP|Co|CO|Ltd|LTD|LLP|Company|COMPANY)\b(?!-)\.?"),
    # judges
    re.compile(rf"{_JUDGE_CUE}\s+{_NAME}"),
    re.compile(rf"{_JUDGE_CUE}\s+[A-Z][A-Za-z.'’-]+(?:\s+[A-Z][A-Za-z.'’-]+)?"),
]
_KNOWN_CASES_RE = re.compile(r"\b(?:" + "|".join(re.escape(n) for n in sorted(_KNOWN_CASE_NAMES, key=len, reverse=True)) + r")\b")
# "Ms. Hubbard", "John Hicks", "J. Kasten": a person who shares a famous case's name
_PERSONAL_PREFIX = re.compile(rf"(?:\b{_TITLES}\.?|\b(?:{_FIRST_RE})|\b[A-Z]\.)[ \t]+$")

# ----------------------------------------------------------------------------------------------
# Regex PII rules: (entity_type, placeholder_prefix, pattern, group)
# ----------------------------------------------------------------------------------------------

_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
_DATE_ANY = (
    rf"(?:{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}|\d{{1,2}}\s+{_MONTH},?\s+\d{{4}}|\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}}|\d{{4}}-\d{{2}}-\d{{2}})"
)
_SUFFIX = r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Way|Place|Pl|Parkway|Pkwy|Circle|Cir|Terrace|Ter|Trail|Trl|Highway|Hwy|Loop|Row|Square|Sq)"
_STREET = (
    rf"\b\d{{1,6}}\s+(?:(?:N|S|E|W|NE|NW|SE|SW|North|South|East|West)\.?\s+)?(?:[A-Z0-9][A-Za-z0-9'’.-]*\s+){{0,3}}[A-Z0-9][A-Za-z0-9'’.-]*\s+{_SUFFIX}\b\.?"
    rf"(?:,?\s*(?:Apt|Apartment|Suite|Ste|Unit|Bldg|Building|Floor|Fl)\.?\s*#?\s*[\w-]+|,?\s*#\s*[\w-]+)?"
    rf"(?:,\s*[A-Z][A-Za-z.' -]+?,\s*(?:[A-Z]{{2}}|Texas|California|New York|Illinois)\b(?:\s+\d{{5}}(?:-\d{{4}})?)?)?"
)

_RULES: list[tuple[str, str, re.Pattern[str], int]] = [
    ("US_SSN", "SSN", re.compile(r"(?<![\d-])\d{3}[- ]\d{2}[- ]\d{4}(?![\d-])"), 0),
    ("US_SSN", "SSN", re.compile(r"(?i)\b(?:SSN|social security(?: number| no\.?)?|SS#)\s*[:#]?\s*(\d{9})\b"), 1),
    ("EMAIL_ADDRESS", "EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"), 0),
    ("PHONE_NUMBER", "PHONE", re.compile(r"(?<![\w-])(?:\+?1[\s.-]?)?(?:\(\d{3}\)\s?|\d{3}[\s.-])\d{3}[\s.-]\d{4}(?![\w-])"), 0),
    ("DATE_OF_BIRTH", "DOB", re.compile(
        rf"(?i)\b(?:D\.?O\.?B\.?|date\s+of\s+birth|birth\s*date|birthday|born(?:\s+on)?)\s*(?:is|was)?\s*[:\-]?\s*({_DATE_ANY})"), 1),
    ("STREET_ADDRESS", "ADDRESS", re.compile(_STREET), 0),
    ("STREET_ADDRESS", "ADDRESS", re.compile(r"(?i)\bP\.?\s?O\.?\s+Box\s+\d+(?:,\s*[A-Z][A-Za-z. ]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?)?"), 0),
    ("ZIP_CODE", "ZIP", re.compile(r"(?<![\d-])\d{5}-\d{4}(?![\d-])"), 0),
    ("US_DRIVER_LICENSE", "LICENSE", re.compile(
        r"(?i)\b(?:driver'?s?\s+licen[sc]e|DL|DLN)\s*(?:no\.?|number|#)?\s*[:#]?\s*([A-Z]?\d[A-Z0-9-]{5,})"), 1),
    ("BANK_ACCOUNT", "ACCOUNT", re.compile(
        r"(?i)\b(?:(?:bank\s+|checking\s+|savings\s+)?account|acct\.?|routing)\s*(?:no\.?|number|#)?\s*[:#]?\s*(\d[\d -]{5,20}\d)"), 1),
    ("CREDIT_CARD", "CARD", re.compile(r"(?<![\d-])(?:\d{4}[ -]){3}\d{4}(?![\d-])|(?<![\d-])\d{4}[ -]\d{6}[ -]\d{5}(?![\d-])"), 0),
    ("ID_NUMBER", "ID", re.compile(
        r"(?i)\b(?:employee|emp\.?|staff|badge|personnel|payroll|worker|member|patient|student|claimant)\s*"
        r"(?:ID|identification|no\.?|number|#)\s*(?:number|no\.?)?\s*(?:is|was)?\s*[:#]?\s*([A-Z]{0,4}-?\d[A-Z0-9-]{2,})"), 1),
    ("ID_NUMBER", "ID", re.compile(r"(?i)\b(?:EEOC\s+)?(?:passport|green card|alien|A-)\s*(?:no\.?|number|#)\s*[:#]?\s*([A-Z]?\d[A-Z0-9-]{5,})"), 1),
    ("LOCATION", "LOCATION", re.compile(
        r"(?i:\b(?:resides|residing|resided|resident of|lives|living|domiciled|reside|live)\s+(?:at|in|near)\s+(?:the\s+city\s+of\s+)?)"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?:,\s*(?:[A-Z]{2}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?))?)"), 1),
]

_PLACEHOLDER = re.compile(r"\[([A-Z]+)_(\d+)\]")
_PREFIX_TYPE = {prefix: etype for etype, prefix, _, _ in _RULES} | {"PERSON": "PERSON", "LOCATION": "LOCATION", "NRP": "NRP"}

_RES_CUE = re.compile(r"(?i)(?:resides|residing|resided|resident of|lives|living|domiciled|reside|live|home (?:in|at)|moved to|relocated to)\s+(?:at|in|near)?\s*(?:the\s+city\s+of\s+)?$")

# ----------------------------------------------------------------------------------------------
# Data structures
# ----------------------------------------------------------------------------------------------


@dataclass
class _Span:
    start: int
    end: int
    etype: str
    prefix: str
    score: float = 1.0
    tokens: frozenset[str] = field(default_factory=frozenset)  # persons only
    value: str = ""
    plaintiff: bool = False


def _tokens_of(text: str) -> frozenset[str]:
    out = set()
    for t in re.findall(r"[A-Za-z][A-Za-z'’-]*", text):
        low = t.lower().strip("'’-")
        if len(low) >= 2 and low not in _STOP_TOKENS and low not in {"mr", "mrs", "ms", "miss", "mx", "dr"}:
            out.add(low)
    return frozenset(out)


def _is_allcaps_line(line: str) -> bool:
    letters = [c for c in line if c.isalpha()]
    return len(letters) >= 4 and sum(c.isupper() for c in letters) / len(letters) > 0.7


def _analysis_text(text: str) -> str:
    """Title-case ALL-CAPS lines (captions) so name rules and spaCy see them as ordinary names.

    str.title() keeps length for ASCII, so offsets are unchanged.
    """
    out = []
    for line in text.split("\n"):
        if _is_allcaps_line(line):
            t = re.sub(r"\b([A-Z])([A-Z']+)\b", lambda m: m.group(1) + m.group(2).lower(), line)
            t = re.sub(r"\bMcd", "McD", t)
            out.append(t if len(t) == len(line) else line)
        else:
            out.append(line)
    return "\n".join(out)


# ----------------------------------------------------------------------------------------------
# Presidio (lazy singleton)
# ----------------------------------------------------------------------------------------------

_analyzer = None
_analyzer_lock = threading.Lock()
_analyzer_error: str | None = None


def presidio_available() -> bool:
    try:
        _get_analyzer()
        return True
    except Exception:
        return False


def _get_analyzer():
    """Build the Presidio analyzer once (spaCy en_core_web_sm only; never the large model)."""
    global _analyzer, _analyzer_error
    if _analyzer is not None:
        return _analyzer
    if _analyzer_error:
        raise RuntimeError(_analyzer_error)
    with _analyzer_lock:
        if _analyzer is not None:
            return _analyzer
        try:
            from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
            from presidio_analyzer.nlp_engine import NlpEngineProvider
            from presidio_analyzer.predefined_recognizers import SpacyRecognizer

            nlp = NlpEngineProvider(nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
            }).create_engine()
            registry = RecognizerRegistry(supported_languages=["en"])
            registry.add_recognizer(SpacyRecognizer(supported_entities=["PERSON", "LOCATION", "NRP"]))
            _analyzer = AnalyzerEngine(nlp_engine=nlp, registry=registry, supported_languages=["en"])
        except Exception as exc:  # pragma: no cover - environment dependent
            _analyzer_error = f"Presidio unavailable: {type(exc).__name__}"
            raise RuntimeError(_analyzer_error) from exc
    return _analyzer


# ----------------------------------------------------------------------------------------------
# Redactor
# ----------------------------------------------------------------------------------------------


class PIIRedactor:
    def __init__(self, engine: Literal["auto", "presidio", "regex"] = "auto", *, redact_nrp: bool = False):
        if engine not in ("auto", "presidio", "regex"):
            raise ValueError(f"unknown redaction engine {engine!r}")
        self.engine_requested = engine
        self.redact_nrp = redact_nrp  # nationality/religion is usually a pleaded fact, so off by default
        self._use_presidio = False
        if engine == "presidio":
            _get_analyzer()  # raises if unavailable
            self._use_presidio = True
        elif engine == "auto":
            self._use_presidio = presidio_available()
            if not self._use_presidio:
                log.warning("Presidio not available; falling back to the regex redaction engine")

    @property
    def engine(self) -> str:
        return "presidio" if self._use_presidio else "regex"

    # -- public ---------------------------------------------------------------------------------

    def redact(self, text: str, *, keep: set[str] | frozenset[str] = frozenset()) -> RedactionResult:
        """Redact `text`. `keep` holds literal strings (case-insensitive) and/or entity-type names
        (e.g. "LOCATION") that must be left untouched."""
        if not text:
            return RedactionResult(text="", entities=[], engine=self.engine)  # type: ignore[arg-type]
        atext = _analysis_text(text)
        protected = self._protected_spans(atext)
        spans: list[_Span] = []
        spans += self._regex_spans(atext, text)
        persons = self._name_rule_spans(atext)
        if self._use_presidio:
            ps, locs = self._presidio_spans(atext, protected)
            persons += ps
            spans += locs
        persons = [p for p in persons if not _overlaps_any(p, protected) and not self._person_rejected(atext, p)]
        persons = self._sweep_known_names(atext, persons, protected)
        spans += persons
        spans = [s for s in spans if not self._kept(text, s, keep)]
        spans = _resolve_overlaps(spans)
        return self._build(text, spans).model_copy(update={"engine": self.engine})

    def redact_edited(self, text: str, known_types: dict[str, str] | None = None) -> RedactionResult:
        """Re-redact hand-corrected text that already contains placeholders. New identifiers are numbered
        after the placeholders already present (so a newly typed name never reuses [PERSON_1]), and the
        placeholders that were kept still count as redactions. `known_types` maps placeholder -> entity type."""
        known_types = known_types or {}
        res = self.redact(text)
        used: dict[str, int] = {}
        for m in _PLACEHOLDER.finditer(text):
            used[m.group(1)] = max(used.get(m.group(1), 0), int(m.group(2)))
        mapping: dict[str, str] = {}
        parts: list[str] = []
        entities: list[RedactedEntity] = []
        pos = shift = 0
        for e in sorted(res.entities, key=lambda e: e.start):
            ph = e.placeholder
            m = _PLACEHOLDER.fullmatch(ph)
            if m and m.group(1) in used:
                if ph not in mapping:
                    used[m.group(1)] += 1
                    mapping[ph] = f"[{m.group(1)}_{used[m.group(1)]}]"
                ph = mapping[ph]
            parts += [res.text[pos:e.start], ph]
            start = e.start + shift
            shift += len(ph) - (e.end - e.start)
            entities.append(e.model_copy(update={"placeholder": ph, "start": start, "end": start + len(ph)}))
            pos = e.end
        parts.append(res.text[pos:])
        out = "".join(parts)
        fresh = [(e.start, e.end) for e in entities]
        for m in re.finditer(r"\[(?:PLAINTIFF|[A-Z]+_\d+)\]", out):
            if not _overlaps(m.span(), fresh):
                prefix = _PLACEHOLDER.fullmatch(m.group(0))
                etype = known_types.get(m.group(0)) or ("PERSON" if prefix is None else _PREFIX_TYPE.get(prefix.group(1), prefix.group(1)))
                entities.append(RedactedEntity(entity_type=etype, placeholder=m.group(0), start=m.start(), end=m.end()))
        entities.sort(key=lambda e: e.start)
        return RedactionResult(text=out, entities=entities, engine=res.engine)

    # -- candidate generation -------------------------------------------------------------------

    @staticmethod
    def _protected_spans(atext: str) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        for pat in _PROTECT_PATTERNS:
            for m in pat.finditer(atext):
                if m.end() > m.start():
                    out.append((m.start(), m.end()))
        # Famous case names ("Hicks", "Hubbard") are protected unless the document also uses the name for a person;
        # then only full citations (protected above) keep it, and every other mention is treated as the person's.
        known = list(_KNOWN_CASES_RE.finditer(atext))
        personal = {m.group(0) for m in known if _PERSONAL_PREFIX.search(atext[max(0, m.start() - 20):m.start()])}
        out += [m.span() for m in known if m.group(0) not in personal]
        # learn short company names from "Acme Logistics, Inc." -> "Acme"
        for m in re.finditer(rf"\b([A-Z][\w&'-]+)(?:\s+[A-Z][\w&'-]+){{0,2}},?\s+{_ORG_SUFFIX}(?=\W|$)", atext):
            word = m.group(1)
            if word.lower() in _STOP_TOKENS:
                continue
            for w in re.finditer(rf"\b{re.escape(word)}\b(?:\s+(?:{_ORG_SUFFIX}))?", atext):
                out.append((w.start(), w.end()))
        return out

    @staticmethod
    def _regex_spans(atext: str, text: str) -> list[_Span]:
        out: list[_Span] = []
        for etype, prefix, pat, grp in _RULES:
            for m in pat.finditer(text):
                s, e = m.span(grp)
                if e <= s:
                    continue
                if etype == "PHONE_NUMBER" and not re.search(r"\d{3}\D*\d{3}\D*\d{4}", m.group(0)):
                    continue
                out.append(_Span(s, e, etype, prefix, value=re.sub(r"\W+", "", text[s:e]).lower()))
        return out

    @staticmethod
    def _name_rule_spans(atext: str) -> list[_Span]:
        out: list[_Span] = []

        def add(s: int, e: int, plaintiff: bool = False) -> None:
            while True:  # trim leading sentence words ("Complaint Maria Rivera")
                m0 = re.match(r"([A-Za-z]+)[ \t]+(?=\S)", atext[s:e])
                if m0 and m0.group(1).lower() in _STOP_TOKENS and m0.group(1).lower() not in {"mr", "mrs", "ms", "miss", "dr", "mx"}:
                    s += m0.end()
                else:
                    break
            val = atext[s:e]
            toks = _tokens_of(val)
            if not toks:
                return
            first = re.findall(r"[A-Za-z][A-Za-z'’-]*", val)
            if first and first[0].lower() in _STOP_TOKENS and not re.match(rf"{_TITLES}\b", val):
                return
            out.append(_Span(s, e, "PERSON", "PERSON", tokens=toks, value=val.lower(), plaintiff=plaintiff))

        # titled: "Ms. Rivera", "Mr. Daniel Okafor"
        for m in re.finditer(rf"\b{_TITLES}\.?\s+({_NAME})", atext):
            if m.group(1).split()[0].lower() in _STOP_TOKENS:
                continue
            add(m.start(), m.end())
        # "Plaintiff Maria Rivera" / "Plaintiff, Maria Rivera"
        for m in re.finditer(rf"\bPlaintiffs?,?[ \t]+({_FULLU})(?=[\s,.;:)]|$)", atext):
            add(m.start(1), m.end(1), plaintiff=True)
        # "MARIA RIVERA, Plaintiff" (name ends the previous line or the same line)
        for m in re.finditer(rf"(?m)({_FULLU}),?[ \t]*(?:\n[ \t]*)?(?:an individual,?\s*)?Plaintiff\b", atext):
            add(m.start(1), m.end(1), plaintiff=True)
        # individual defendants "John Smith, Defendant"
        for m in re.finditer(rf"(?m)({_FULLU}),?[ \t]*(?:\n[ \t]*)?(?:an individual,?\s*)?Defendant\b", atext):
            add(m.start(1), m.end(1))
        # role cue + name
        for m in re.finditer(rf"(?i:\b(?:{_ROLE_CUES}))\s+({_FULL}|{_TOK}(?=[\s,.;:)]))", atext):
            if m.group(1).split()[0].lower() in _STOP_TOKENS:
                continue
            add(m.start(1), m.end(1))
        # common first name (+ initial) + surname
        for m in re.finditer(rf"\b(?:{_FIRST_RE})\s+(?:[A-Z]\.\s+)?(?:{_TOK}\b)(?:\s+{_TOK}\b)?", atext):
            add(m.start(), m.end())
        # "first name alone" is handled by the known-name sweep
        return out

    def _presidio_spans(self, atext: str, protected: list[tuple[int, int]]) -> tuple[list[_Span], list[_Span]]:
        analyzer = _get_analyzer()
        entities = ["PERSON", "LOCATION"] + (["NRP"] if self.redact_nrp else [])
        persons: list[_Span] = []
        locs: list[_Span] = []
        for r in analyzer.analyze(text=atext, language="en", entities=entities):
            val = atext[r.start:r.end]
            if r.entity_type == "PERSON":
                # absorb a preceding title ("Ms. Rivera")
                s = r.start
                tm = re.search(rf"\b{_TITLES}\.?\s+$", atext[max(0, s - 8):s])
                if tm:
                    s -= len(tm.group(0))
                nl = val.find("\n")
                end = r.end if nl < 0 else r.start + nl  # never span a line break
                val = atext[r.start:end]
                persons.append(_Span(s, end, "PERSON", "PERSON", float(r.score), _tokens_of(val), val.lower()))
            elif r.entity_type == "LOCATION":
                if _RES_CUE.search(atext[max(0, r.start - 40):r.start]) and not _overlaps((r.start, r.end), protected):
                    locs.append(_Span(r.start, r.end, "LOCATION", "LOCATION", float(r.score),
                                      value=val.lower()))
            elif r.entity_type == "NRP":
                locs.append(_Span(r.start, r.end, "NRP", "NRP", float(r.score), value=val.lower()))
        return persons, locs

    @staticmethod
    def _person_rejected(atext: str, p: _Span) -> bool:
        val = atext[p.start:p.end]
        if re.search(r"\d", val) or len(val) > 60 or len(val.split()) > 5:
            return True
        words = [w.lower().strip(".,'’") for w in re.findall(r"[A-Za-z][A-Za-z'’.-]*", val)]
        if all(w in _STOP_TOKENS for w in words):
            return True
        if not p.tokens:
            return True
        return False

    @staticmethod
    def _sweep_known_names(atext: str, persons: list[_Span], protected: list[tuple[int, int]]) -> list[_Span]:
        """Find further bare mentions ("Rivera", "Maria") of every name already detected."""
        if not persons:
            return persons
        have = {(p.start, p.end) for p in persons}
        words: set[str] = set()
        for p in persons:
            for w in re.findall(r"[A-Za-z][A-Za-z'’-]+", atext[p.start:p.end]):
                low = w.lower()
                if len(low) >= 3 and low not in _STOP_TOKENS and low not in {"mrs", "miss"}:
                    words.add(low)
        out = list(persons)
        if words:
            pat = re.compile(r"\b(" + "|".join(sorted(map(re.escape, words), key=len, reverse=True)) + r")\b", re.I)
            for m in pat.finditer(atext):
                s, e = m.span()
                w = m.group(1)
                if not (w[0].isupper()):
                    continue
                if any(ps <= s and e <= pe for ps, pe in have) or _overlaps((s, e), protected):
                    continue
                # a title just before is absorbed into the span
                tm = re.search(rf"\b{_TITLES}\.?\s+$", atext[max(0, s - 8):s])
                ss = s - len(tm.group(0)) if tm else s
                out.append(_Span(ss, e, "PERSON", "PERSON", 0.8, _tokens_of(w), w.lower()))
        return out

    @staticmethod
    def _kept(text: str, s: _Span, keep) -> bool:
        if not keep:
            return False
        kl = {k.lower() for k in keep}
        return s.etype.lower() in kl or text[s.start:s.end].lower() in kl

    # -- assembly -------------------------------------------------------------------------------

    @staticmethod
    def _build(text: str, spans: list[_Span]) -> RedactionResult:
        spans.sort(key=lambda s: s.start)
        # cluster persons by shared name tokens (union-find)
        parent: dict[str, str] = {}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for s in spans:
            if s.etype != "PERSON":
                continue
            toks = list(s.tokens)
            for t in toks:
                parent.setdefault(t, t)
            for t in toks[1:]:
                parent[find(t)] = find(toks[0])
        plaintiff_roots = {find(t) for s in spans if s.etype == "PERSON" and s.plaintiff for t in s.tokens}

        counters: dict[str, int] = {}
        assigned: dict[tuple[str, str], str] = {}
        out_parts: list[str] = []
        entities: list[RedactedEntity] = []
        pos = 0
        out_len = 0
        for s in spans:
            if s.etype == "PERSON":
                root = find(next(iter(s.tokens)))
                key = ("PERSON", root)
                if root in plaintiff_roots:
                    ph = "[PLAINTIFF]"
                else:
                    ph = assigned.get(key) or ""
            else:
                key = (s.etype, s.value)
                ph = assigned.get(key, "")
            if not ph:
                counters[s.prefix] = counters.get(s.prefix, 0) + 1
                ph = f"[{s.prefix}_{counters[s.prefix]}]"
            assigned[key] = ph
            chunk = text[pos:s.start]
            out_parts.append(chunk)
            out_len += len(chunk)
            out_parts.append(ph)
            entities.append(RedactedEntity(entity_type=s.etype, placeholder=ph, start=out_len,
                                           end=out_len + len(ph), score=s.score))
            out_len += len(ph)
            pos = s.end
        out_parts.append(text[pos:])
        return RedactionResult(text="".join(out_parts), entities=entities)


def _overlaps(span: tuple[int, int], others: list[tuple[int, int]]) -> bool:
    s, e = span
    return any(s < oe and os_ < e for os_, oe in others)


def _overlaps_any(p: _Span, protected: list[tuple[int, int]]) -> bool:
    return _overlaps((p.start, p.end), protected)


_PRIORITY = {"US_SSN": 0, "CREDIT_CARD": 1, "EMAIL_ADDRESS": 2, "DATE_OF_BIRTH": 3, "US_DRIVER_LICENSE": 4,
             "BANK_ACCOUNT": 5, "ID_NUMBER": 6, "PHONE_NUMBER": 7, "STREET_ADDRESS": 8, "ZIP_CODE": 9,
             "LOCATION": 10, "PERSON": 11, "NRP": 12}


def _resolve_overlaps(spans: list[_Span]) -> list[_Span]:
    """Keep non-overlapping spans: structured identifiers first, then the longest span."""
    ordered = sorted(spans, key=lambda s: (_PRIORITY.get(s.etype, 20), -(s.end - s.start), s.start))
    chosen: list[_Span] = []
    for s in ordered:
        if not any(s.start < c.end and c.start < s.end for c in chosen):
            chosen.append(s)
    return sorted(chosen, key=lambda s: s.start)
