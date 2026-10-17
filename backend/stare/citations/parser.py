"""Gate 1: extract citations (eyecite) and attach the case name and the quoted text."""

from __future__ import annotations

import logging
import re

from eyecite import get_citations, resolve_citations
from eyecite.models import (
    FullCaseCitation,
    FullLawCitation,
    IdCitation,
    ShortCaseCitation,
)

from stare.citations.reporters import normalize_reporter
from stare.schemas import ExtractedCitation

logging.getLogger("eyecite").setLevel(logging.ERROR)

_SIGNALS = re.compile(
    r"^(?:(?:see|see also|see, e\.g\.,|accord|cf\.|but see|but cf\.|compare|contra|e\.g\.,|also|and|"
    r"citing|quoting|in(?!\s+re\b)|under|per|with)\s+)+",
    re.IGNORECASE,
)
_IN_RE = re.compile(r"((?:In re|Ex parte|Matter of)\s+[^,;()]{1,100}?)\s*,\s*$")
_ABBREVS = frozenset(
    ["inc", "co", "corp", "ltd", "mfg", "ky", "tex", "sw", "med", "ctr", "univ", "dept", "assn", "bros", "intl", "natl", "fla", "ill", "ga", "cal", "mass", "pa", "wash", "mich", "ind", "ala", "miss", "okla", "ariz", "colo", "conn", "dist", "comm", "govt", "hosp", "inst", "ins", "indus", "mgmt", "serv", "sys", "sch", "st", "cnty", "ex", "rel", "no", "nos", "cir", "ct", "app", "supp", "fed", "cl", "mr", "mrs", "ms", "dr", "jr", "sr", "prof", "hon", "esq", "cf", "ed", "eds", "div", "sec", "stat", "art", "cong", "rep", "sen", "gen", "lt", "col", "sgt", "mt", "ft", "vs", "pub", "sess", "pt", "para", "compl", "dkt", "ecf", "exh", "tr", "nat", "ass", "ala", "ark", "del", "haw", "ida", "kan", "minn", "mont", "neb", "nev", "okl", "ore", "tenn", "vt", "wis", "wyo", "ne", "se", "nw", "nd", "sd", "ed", "wd", "md", "cd", "dc"]
)
# Bluebook T6 / T10 words that end in a period inside case names ("Tex. Dep't of Cmty. Affairs v. Burdine")
_T6 = """adm admin advert agric am ams arb assocs atl auth auto ave bankr bd bldg bhd cas cath cent chem cmty
coll cont coop crim def dev dir distrib dist econ educ elec emp eng'g ent envtl equip exch exec fid fin
gen grp guar hous immigr indem indep info inv invs lab litig loc mach mar med merch metro mfrs mkt mktg mortg mun mut
natl navig ord org pac pers pharm pol prob prod prods prop prot ry rsch rts sav sch scis sec ser servs soc
sol stat sur sw tech tel transp twp unif util ass'n comm'n dep't gov't int'l nat'l soc'y att'y emp'r emp'rs ass'ns
fed'n env't def't""".split()
_ABBREVS = _ABBREVS | frozenset(_T6) | frozenset(w.replace("'", "’") for w in _T6 if "'" in w)
_SENT_END = re.compile(r"[.!?][\"”')\]]*\s+(?=[A-Z“\"(\[])")
_WORD_BEFORE = re.compile(r"([A-Za-z][A-Za-z.'’]*)$")


def sentence_starts(text: str, protected: list[tuple[int, int]] | None = None) -> list[int]:
    """Offsets at which a new sentence (or blank-line separated paragraph) begins. Abbreviations
    ('Inc.', 'Cir.', 'v.', initials) and periods inside protected spans (citations) are not breaks."""
    protected = protected or []
    starts = [0]
    for m in re.finditer(r"\n\s*\n", text):
        starts.append(m.end())
    for m in _SENT_END.finditer(text):
        i = m.start()
        if any(s < i < e for s, e in protected):
            continue
        if text[i] == "." and i > 0 and text[i - 1].isalnum():
            w = _WORD_BEFORE.search(text[max(0, i - 30):i])
            if w:
                word = w.group(1).lower()
                if "." in word or len(word) == 1 or word in _ABBREVS:
                    continue
        starts.append(m.end())
    return sorted(set(starts))


def _last_sentence(s: str) -> str:
    starts = sentence_starts(s)
    return s[starts[-1]:]


_CONNECT = {"of", "the", "and", "for", "ex", "rel.", "rel", "de", "la", "del", "&", "on", "to", "at", "in"}


def _plaintiff_tail(side: str) -> str:
    """Trailing run of name-like tokens: 'as held in Smith' -> 'Smith'; 'Title VII, Smith' -> 'Smith'."""
    toks = side.split()
    keep = len(toks)
    i = len(toks) - 1
    while i >= 0:
        t = toks[i]
        bare = t.strip(",;:()\"“”")
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        ok = bool(bare) and (bare[0].isupper() or bare[0].isdigit() or bare.lower() in _CONNECT - {"in", "on", "to", "at"})
        if ok and t.endswith(",") and i + 1 < len(toks):
            joined = bare.endswith(".") or re.match(r"(?:Inc|Co|Corp|Ltd|L\.L\.C|LLC|LLP|L\.P|LP|FSB|N\.A|NA|S\.A|P\.C|PC|PLLC|P\.A|Jr|Sr|II|III|&)\b", nxt) or nxt == "&"
            if not joined:
                break
        if not ok:
            break
        keep = i
        i -= 1
    out = toks[keep:]
    while out and out[0].lower().strip(",") in _CONNECT:
        out = out[1:]
    return " ".join(out)


def _case_name_before(text: str, cite_start: int) -> tuple[str, int]:
    """Case name from the text preceding the reporter cite: 'See Smith v. Jones, ' -> ('Smith v. Jones', offset)."""
    lo = max(0, cite_start - 260)
    window = text[lo:cite_start]
    last = _last_sentence(window)
    if ";" in last:  # string citation: "A v. B, 1 F.3d 2 (1999); C v. D, ..." -> only the part after the last ';'
        last = last[last.rfind(";") + 1:]
    base = lo + len(window) - len(last)
    seg = last.rstrip()
    if not seg.endswith(","):
        return "", cite_start
    seg = seg.rstrip(", ")
    m = None
    for m in re.finditer(r"\s+v\.?\s+", seg):
        pass
    if m is None:
        im = _IN_RE.search(seg + ",")
        if im:
            name = _strip_signals(im.group(1))
            return name, text.rfind(name, lo, cite_start)
        return "", cite_start
    plaintiff = _plaintiff_tail(_strip_signals(seg[: m.start()]))
    defendant = seg[m.end():].strip()
    if not plaintiff or not defendant:
        return "", cite_start
    name = f"{plaintiff} v. {defendant}"
    # offset of the plaintiff's first token inside the text
    start = seg[: m.start()].rfind(plaintiff.split()[0] if plaintiff.split() else plaintiff)
    start = base + (max(start, 0))
    # make sure we start at the true token start of the plaintiff phrase
    idx = text.rfind(plaintiff, lo, cite_start)
    if idx >= 0:
        start = idx
    return name, start


_TAIL_RE = re.compile(
    r"^(?P<pin>(?:\s*,\s*(?:at\s+)?\*?\d+(?:[-–]\d+)?(?:\s*&\s*n\.\s*\d+)?)*)"
    r"(?P<par>\s*\((?P<inner>[^()]{0,80}?)(?P<yr>(?:1[6-9]|20)\d\d)\))?"
)


def _tail(text: str, ce: int) -> tuple[int, str | None, str | None, int | None]:
    """After the reporter cite: pin cite, '(court year)' parenthetical. Returns (end, pin, court, year)."""
    m = _TAIL_RE.match(text[ce:ce + 200])
    if not m:
        return ce, None, None, None
    pin = m.group("pin").strip(" ,") or None
    if pin:
        pin = re.sub(r"^at\s+", "", pin)
    court = year = None
    if m.group("par"):
        court = re.sub(r"\b" + _MONTH + r"\s*\d{0,2},?", "", m.group("inner")).strip(" ,") or None
        year = int(m.group("yr"))
    return ce + m.end(), pin, court, year


# --- statutes and regulations ------------------------------------------------------------------
_LAW_RE = re.compile(
    r"(?P<title>\d{1,2})\s+(?P<code>U\.\s?S\.\s?C\.(?:\s?A\.)?|C\.\s?F\.\s?R\.)\s*"
    r"(?:§§?\s*|sec(?:tion)?s?\.?\s+)?"
    r"(?P<sec>\d+[a-zA-Z]{0,2}(?:[-–]\d+[a-zA-Z]{0,2})?(?:\.\d+[a-z]?)?)"
    r"(?P<sub>(?:\([A-Za-z0-9]{1,4}\))*)"
)

# --- neutral / vendor citations eyecite may miss -------------------------------------------------
_NEUTRAL_RE = re.compile(
    r"\b(?P<year>(?:19|20)\d{2})\s+(?P<rep>(?:IL|Ill\.)\s+App\.?(?:\s*\(\d(?:st|nd|rd|th)\))?|WL|"
    r"U\.S\.\s+(?:Dist|App)\.\s+LEXIS|Tex\.\s+App\.\s+LEXIS|"
    r"(?:Ohio|OH|NM|ND|SD|UT|WI|WY|MT|ME|VT|CO|PA|IN|LA|MN|OK|MS|AR|SC|TX|NY|NC|WV|MD|KS|AZ|AK|CT|DE|HI|ID|IA|KY|MI|MO|NE|NV|NH|NJ|OR|RI|TN|VA|WA)"
    r"(?:\s+App\.?)?)\s+(?P<page>\d[\w\-]*)"
)

_QUOTE_RE = re.compile(r"“([^”]{3,}?)”|\"([^\"]{3,}?)\"", re.DOTALL)
_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"


def _strip_signals(s: str) -> str:
    return _SIGNALS.sub("", s.strip())


def _canonical(volume: str, reporter: str, page: str) -> str:
    return f"{volume} {reporter} {page}".strip()


def _find_quotes(text: str) -> list[tuple[int, int, str]]:
    out = []
    for m in _QUOTE_RE.finditer(text):
        inner = (m.group(1) or m.group(2) or "").strip()
        if len(inner.split()) >= 3:
            out.append((m.start(), m.end(), inner))
    return out


_BOUNDARY = re.compile(r"[.!?][\"”')\]]*\s+(?=[A-Z])|\n\s*\n")


def _gap_ok(gap: str) -> bool:
    """True when the text between a quote and a citation stays inside one sentence."""
    if "\n\n" in gap:
        return False
    return not re.search(r"(?<![A-Z])(?<!\bInc)(?<!\bCo)(?<!\bv)(?<!\bCir)[.!?]\s+[A-Z]", gap) and len(gap) <= 220


def _outside_parens(s: str) -> str:
    """Text with (nested) parentheticals removed: a ';' inside '(Supreme Court; binds ...)' does not separate citations."""
    prev = None
    while prev != s:
        prev, s = s, re.sub(r"\([^()]*\)", "", s)
    return s


def _attach_quotes(cites: list[ExtractedCitation], text: str) -> None:
    quotes = _find_quotes(text)
    spans = [c.span for c in cites]
    assigned: dict[int, list[tuple[int, str]]] = {}
    for qs, qe, inner in quotes:
        best: tuple[tuple[int, int], int] | None = None  # ((preceding?, distance), cite index)
        for i, (cs, ce) in enumerate(spans):
            if cs >= qe:
                gap = text[qe:cs]
            elif ce <= qs:
                gap = text[ce:qs]
            else:  # citation inside the quote or overlapping: ignore
                continue
            if not _gap_ok(gap):
                continue
            if cs >= qe:
                if re.search(r"[.!?][\"”')\]]*\s*$", gap):
                    continue  # the cite starts a new sentence
                # quote precedes the cite. If the quote closes its sentence, only a bare citation sentence
                # ("\"...\" Smith v. Jones, ...", optionally after a signal) belongs to it.
                if inner.rstrip().endswith((".", "?", "!")) and not re.fullmatch(
                    r"\s*(?:(?:See|See also|Cf\.|Accord|But see|e\.g\.,)\s+)*", gap, re.IGNORECASE
                ):
                    continue
            elif re.search(r"[.!?][\"”')\]]*\s*$", gap):
                continue  # quote starts a new sentence after the citation
            # another citation between the quote and this one makes the association ambiguous
            lo, hi = (qe, cs) if cs >= qe else (ce, qs)
            if any(j != i and lo <= spans[j][0] and spans[j][1] <= hi for j in range(len(spans))):
                continue
            d = 0 if (cs < qe and re.search(r"\(\s*(?:[\w,]+\s+){0,4}$", gap)) else len(gap)  # explanatory parenthetical
            # A citation that introduces the quote in the same sentence ("In X, 1 U.S. 1, the court explained:
            # "...".") owns it; a following citation sentence ("See Y ...") only claims quotes no citation introduced.
            preceding = cs < qe and ";" not in _outside_parens(gap)
            key = (0 if preceding else 1, d)
            if best is None or key < best[0]:
                best = (key, i)
        if best:
            assigned.setdefault(best[1], []).append((qs, inner))
    for i, qs in assigned.items():
        qs.sort()
        cites[i].quote = " ... ".join(q for _, q in qs)


def _law_cites(text: str) -> list[ExtractedCitation]:
    out = []
    for m in _LAW_RE.finditer(text):
        code = re.sub(r"[\s.]", "", m.group("code")).upper()
        is_cfr = code.startswith("CFR")
        reporter = "C.F.R." if is_cfr else "U.S.C."
        sec = m.group("sec").replace("–", "-")
        title = m.group("title")
        out.append(
            ExtractedCitation(
                raw=m.group(0).strip(),
                cite=f"{title} {reporter} § {sec}",
                volume=title,
                reporter=reporter,
                page=sec,
                pin_cite=m.group("sub") or None,
                span=(m.start(), m.end()),
                kind="regulation" if is_cfr else "statute",
            )
        )
    return out


_EMPHASIS = re.compile(r"\*+(?=[A-Za-z(])|(?<=[A-Za-z.,)])\*+")


def extract_citations(text: str) -> list[ExtractedCitation]:
    """Gate 1. Returns citations in document order with case name, year, court hint, pin cite and quote."""
    if not text:
        return []
    # Markdown emphasis ("*Smith v. Jones*, 1 U.S. 1") hides case names from the parser. Replace the
    # asterisks with spaces (same length, so spans stay valid); Westlaw star pages ("at *3") are kept.
    text = _EMPHASIS.sub(" ", text)
    raw_cites = get_citations(text)
    laws = _law_cites(text)
    law_spans = [c.span for c in laws]

    def overlaps(a: tuple[int, int], spans) -> bool:
        return any(a[0] < e and s < a[1] for s, e in spans)

    items: list[tuple[object, ExtractedCitation]] = []
    for c in raw_cites:
        if isinstance(c, FullCaseCitation):
            g = c.groups
            volume, rep, page = str(g.get("volume") or ""), normalize_reporter(str(g.get("reporter") or "")), str(g.get("page") or "")
            cs, ce = c.span()
            name, start = _case_name_before(text, cs)
            if not name:
                md = c.metadata
                if getattr(md, "plaintiff", None) and getattr(md, "defendant", None):
                    name = f"{md.plaintiff} v. {md.defendant}".replace("  ", " ")
            end, pin, court, year = _tail(text, ce)
            if year is None and c.metadata.year:
                year = int(c.metadata.year)
            ec = ExtractedCitation(
                raw=text[start:end].strip(),
                cite=_canonical(volume, rep, page),
                volume=volume, reporter=rep, page=page,
                pin_cite=pin or getattr(c.metadata, "pin_cite", None),
                case_name=name, year=year, court_hint=court,
                span=(start, end), kind="case",
            )
            items.append((c, ec))
        elif isinstance(c, ShortCaseCitation):
            g = c.groups
            cs, ce = c.span()
            rep = normalize_reporter(str(g.get("reporter") or ""))
            ec = ExtractedCitation(
                raw=text[cs:ce], cite=_canonical(str(g.get("volume")), rep, str(g.get("page"))),
                volume=str(g.get("volume")), reporter=rep, page=str(g.get("page")),
                pin_cite=getattr(c.metadata, "pin_cite", None), span=(cs, ce), kind="short_form",
            )
            items.append((c, ec))
        elif isinstance(c, IdCitation):
            cs, ce = c.span()
            pm = re.match(r"\s*(?:at\s+\*?\d+(?:[-–]\d+)?(?:\s*&\s*n\.\s*\d+)?)", text[ce:ce + 40])
            end = ce + (pm.end() if pm else 0)
            pm2 = re.search(r"\bat\s+(\*?\d.*)$", text[cs:end])
            pin = pm2.group(1).strip() if pm2 else None
            ec = ExtractedCitation(raw=text[cs:end].strip(), cite="", pin_cite=pin, span=(cs, end), kind="id")
            items.append((c, ec))
        elif isinstance(c, FullLawCitation):
            continue  # handled by the regex pass (eyecite misses sections such as 2000e-3)

    # fallback for neutral / vendor cites eyecite did not return
    covered = [ec.span for _, ec in items] + law_spans
    for m in _NEUTRAL_RE.finditer(text):
        if overlaps(m.span(), covered):
            continue
        rep = normalize_reporter(m.group("rep"))
        cs, ce = m.span()
        end, pin, court, year = _tail(text, ce)
        name, start = _case_name_before(text, cs)
        ec = ExtractedCitation(
            raw=text[start:end].strip(), cite=_canonical(m.group("year"), rep, m.group("page")),
            volume=m.group("year"), reporter=rep, page=m.group("page"), pin_cite=pin,
            case_name=name, year=year or int(m.group("year")), court_hint=court, span=(start, end), kind="case",
        )
        items.append((None, ec))

    items = [(c, ec) for c, ec in items if not overlaps(ec.span, law_spans)]
    items += [(None, ec) for ec in laws]
    items.sort(key=lambda p: p[1].span[0])

    # resolve short forms with eyecite; ids are resolved to the preceding authority in document order
    eye_items = [c for c, _ in items if c is not None]
    resolution: dict[int, ExtractedCitation] = {}
    try:
        res = resolve_citations(eye_items)
    except Exception:  # pragma: no cover - eyecite resolution is best effort
        res = {}
    by_eye = {id(c): ec for c, ec in items if c is not None}
    for resource, group in res.items():
        full = next((x for x in group if isinstance(x, FullCaseCitation)), None)
        if full is None or id(full) not in by_eye:
            continue
        for x in group:
            if isinstance(x, ShortCaseCitation):
                resolution[id(x)] = by_eye[id(full)]

    out: list[ExtractedCitation] = []
    prev: ExtractedCitation | None = None
    fulls: list[ExtractedCitation] = []
    for c, ec in items:
        if ec.kind == "short_form":
            ante = resolution.get(id(c)) or next(
                (f for f in reversed(fulls) if f.volume == ec.volume and f.reporter == ec.reporter), None
            )
            if ante is not None:
                # "570 U.S. at 362" refers to the case at 570 U.S. 338; 362 is only the pin page
                ec.pin_cite = ec.pin_cite or ec.page
                ec.cite, ec.page = ante.cite, ante.page
                ec.case_name, ec.year, ec.court_hint = ante.case_name, ante.year, ante.court_hint
        elif ec.kind == "id":
            if prev is not None:
                a = prev
                ec.cite, ec.volume, ec.reporter, ec.page = a.cite, a.volume, a.reporter, a.page
                ec.case_name, ec.year, ec.court_hint = a.case_name, a.year, a.court_hint
        else:
            fulls.append(ec)
        out.append(ec)
        prev = ec if ec.kind != "id" or ec.cite else prev
    _attach_quotes(out, text)
    return out
