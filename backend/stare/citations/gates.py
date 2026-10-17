"""The four gates of the Citation Firewall. Each returns a GateResult (gate_exists also the match)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from stare.citations.cap_static import CAPStaticClient
from stare.citations.courtlistener import CourtListenerClient
from stare.citations.index import CitationIndex
from stare.citations.quote import match_quote
from stare.citations.reporters import case_name_similarity
from stare.citations.treatment import has_authority_over, mention_patterns, scan_context
from stare.config import Settings, get_settings
from stare.db.models import Citation, CitationEdge, Opinion, Treatment
from stare.schemas import ExtractedCitation, GateResult
from stare.text import majority_text

_LAW_REPORTERS = {"U.S.C.", "C.F.R."}


def is_law(cite: ExtractedCitation) -> bool:
    return cite.kind in ("statute", "regulation") or (cite.reporter or "") in _LAW_REPORTERS


@dataclass
class OpinionRef:
    """What Gate 2 found at the cited location."""

    case_name: str
    cite: str
    source: str  # local | cache | courtlistener | statute_index
    opinion_id: int | None = None
    cluster_id: int | None = None
    section_id: int | None = None
    year: int | None = None
    url: str | None = None
    cap_path: str | None = None  # static.case.law case file when found through CAP


# ----------------------------------------------------------------------------------------------
# Gate 1
# ----------------------------------------------------------------------------------------------


def gate_extract(cite: ExtractedCitation) -> GateResult:
    if cite.kind in ("id", "short_form") and not (cite.volume and cite.reporter and cite.page):
        return GateResult(gate=1, name="extract", outcome="fail", detail=f"'{cite.raw}' has no antecedent citation")
    if not (cite.volume and cite.reporter and cite.page):
        return GateResult(gate=1, name="extract", outcome="fail", detail=f"could not parse a volume/reporter/page from '{cite.raw}'")
    extra = "" if (is_law(cite) or cite.case_name) else "; no case name given"
    return GateResult(gate=1, name="extract", outcome="pass", detail=f"parsed {cite.cite}{extra}")


# ----------------------------------------------------------------------------------------------
# Gate 2
# ----------------------------------------------------------------------------------------------


def _g2(outcome: str, detail: str, score: float | None = None) -> GateResult:
    return GateResult(gate=2, name="exists", outcome=outcome, detail=detail, score=score)  # type: ignore[arg-type]


def _judge(cite: ExtractedCitation, found: list[tuple[str, int | None, str]], threshold: float):
    """found: [(case_name, year, label)]. Returns (best_index, score, outcome, detail)."""
    name = cite.case_name
    if not name:
        return 0, None, "warn", f"{cite.cite} exists ({found[0][0]}), but the draft gives no case name so the name could not be checked"
    scored = [(case_name_similarity(name, fn), i) for i, (fn, _, _) in enumerate(found)]
    score, i = max(scored)
    if score < threshold:
        others = "; ".join(f"'{fn}'" for fn, _, _ in found[:3])
        return i, score, "fail", (
            f"{cite.cite} belongs to {others}, not '{name}' (name similarity {score:.2f} < {threshold:.2f}); the citation does not support the case named in the draft"
        )
    fyear = found[i][1]
    if cite.year and fyear and abs(cite.year - fyear) > 1:
        return i, score, "warn", f"case found ({found[i][0]}) but the draft says {cite.year} and the opinion is from {fyear}"
    return i, score, "pass", f"{cite.cite} found: {found[i][0]} (name similarity {score:.2f})"


def gate_exists(
    cite: ExtractedCitation,
    index: CitationIndex,
    client: CourtListenerClient | None,
    settings: Settings | None = None,
    cap: CAPStaticClient | None = None,
) -> tuple[GateResult, OpinionRef | None]:
    """Local citation index -> CAP static reporter listings -> CourtListener (cache, then API).
    Existence AND case-name agreement."""
    settings = settings or get_settings()
    thr = settings.case_name_threshold

    if is_law(cite):
        sec = index.lookup_statute(cite)
        if sec is None:
            return _g2("unresolved", f"{cite.cite} is not in the local statute index; it cannot be verified (not treated as nonexistent)"), None
        ref = OpinionRef(case_name=sec.heading, cite=sec.citation, source="statute_index", section_id=sec.id, url=sec.url)
        return _g2("pass", f"{sec.citation} found in the statute index: {sec.heading}"), ref

    local = index.lookup(cite.volume or "", cite.reporter or "", cite.page or "")
    if local:
        i, score, outcome, detail = _judge(cite, [(o.case_name, o.year, "local") for o in local], thr)
        if outcome == "fail":
            return _g2("fail", detail, score), None
        o = local[i]
        return _g2(outcome, detail, score), OpinionRef(o.case_name, o.citation or cite.cite, "local", opinion_id=o.id, year=o.year, url=o.url)

    cap_res = cap.lookup(cite.volume or "", cite.reporter or "", cite.page or "") if cap else None
    if cap_res == []:
        return _g2("fail", f"no case begins at {cite.cite} in the Caselaw Access Project's listing of that volume"), None
    if cap_res:
        found = [(r["case_name"], _year(r.get("date_filed")), "cap") for r in cap_res]
        i, score, outcome, detail = _judge(cite, found, thr)
        if outcome == "fail":
            return _g2("fail", detail, score), None
        r = cap_res[i]
        return _g2(outcome, detail, score), OpinionRef(r["case_name"], cite.cite, "cap", year=found[i][1], url=r["url"],
                                                      cap_path=r["path"])

    res = client.lookup_citation(cite.volume or "", cite.reporter or "", cite.page or "") if client else None
    if res is None:
        return _g2("unresolved", f"{cite.cite} is not in the local index and CourtListener is unavailable"), None
    if not res:
        if not getattr(client, "last_authoritative", True):
            return _g2("unresolved", f"{cite.cite} was not found in CourtListener's public search index; its existence "
                                     "could not be confirmed (a free CourtListener token enables the authoritative lookup)"), None
        return _g2("fail", f"no matching opinion in index or API for {cite.cite}"), None
    found = [(r.get("case_name") or "", _year(r.get("date_filed")), "api") for r in res]
    i, score, outcome, detail = _judge(cite, found, thr)
    if outcome == "fail":
        return _g2("fail", detail, score), None
    r = res[i]
    src = "cache" if client and client.last_from_cache else "courtlistener"
    return _g2(outcome, detail, score), OpinionRef(r.get("case_name") or "", cite.cite, src, cluster_id=r.get("cluster_id"), year=found[i][1], url=r.get("url"))


def _year(date: str | None) -> int | None:
    m = re.match(r"(\d{4})", date or "")
    return int(m.group(1)) if m else None


# ----------------------------------------------------------------------------------------------
# Gate 3
# ----------------------------------------------------------------------------------------------


def gate_quote_match(quote: str, opinion_text: str, settings: Settings | None = None) -> GateResult:
    settings = settings or get_settings()
    if not (quote or "").strip():
        return GateResult(gate=3, name="quote_match", outcome="skip", detail="no quotation attached to this citation")
    if not (opinion_text or "").strip():
        return GateResult(gate=3, name="quote_match", outcome="unresolved", detail="opinion text unavailable, so the quotation could not be checked")
    court_part = majority_text(opinion_text)
    m = match_quote(quote, court_part)
    if m.score < settings.quote_warn_threshold and len(court_part) < len(opinion_text):
        whole = match_quote(quote, opinion_text)
        if whole.score >= settings.quote_warn_threshold:
            return GateResult(gate=3, name="quote_match", outcome="warn", score=whole.score,
                              detail="quotation appears only in a dissenting or concurring opinion, not in the opinion of the court")
    if m.score >= settings.quote_exact_threshold:
        return GateResult(gate=3, name="quote_match", outcome="pass", detail="quotation found verbatim (after normalisation)", score=m.score)
    if m.score >= settings.quote_warn_threshold:
        return GateResult(gate=3, name="quote_match", outcome="warn", detail=f"quotation is a near match ({m.score:.2f}); compare against the opinion: “{m.matched[:200]}”", score=m.score)
    return GateResult(gate=3, name="quote_match", outcome="fail", detail=f"quotation not found in the opinion (best similarity {m.score:.2f} < {settings.quote_warn_threshold:.2f})", score=m.score)


# ----------------------------------------------------------------------------------------------
# Gate 4
# ----------------------------------------------------------------------------------------------

_MAX_EDGES = 400


@lru_cache(maxsize=1)
def _hierarchy():
    from stare.courts.hierarchy import CourtHierarchy

    return CourtHierarchy.default()


def good_law_findings(
    opinion_id: int | None,
    session: Session,
    client: CourtListenerClient | None = None,
    cluster_id: int | None = None,
) -> tuple[list[str], int]:
    """(treatment strings, number of citing opinions scanned)."""
    out: list[str] = []
    scanned = 0
    if opinion_id is not None:
        for t in session.scalars(select(Treatment).where(Treatment.opinion_id == opinion_id)):
            label = t.kind.replace("_", " ")
            out.append(f"{label}: {t.by}" + (f" ({t.note})" if t.note else ""))
        op = session.get(Opinion, opinion_id)
        cites = [c for c in session.scalars(select(Citation.cite).where(Citation.opinion_id == opinion_id))]
        if op is not None and op.citation:
            cites.append(op.citation)
        pats = mention_patterns(op.case_name if op else "", cites)
        edges = session.scalars(select(CitationEdge).where(CitationEdge.cited_id == opinion_id).limit(_MAX_EDGES)).all()
        for e in edges:
            citing = session.get(Opinion, e.citing_id)
            if citing is None:
                continue
            scanned += 1
            who = f"{citing.case_name} ({citing.citation})" if citing.citation else citing.case_name
            if (e.treatment or "").startswith("negative"):
                kind = e.treatment.split(":", 1)[-1] or "negative treatment"
                out.append(f"{kind} by {who}")
                continue
            if op is not None and not has_authority_over(citing.court_id, op.court_id, _hierarchy()):
                continue  # e.g. a court of appeals cannot overrule the Supreme Court
            found = scan_context(e.context or "", pats, require_mention=False, limit=1) or scan_context(
                citing.plain_text or "", pats, limit=1
            )
            if found:
                f = found[0]
                out.append(f"{f.label} by {who}: “{f.snippet[:220]}”")
    if client is not None and cluster_id is not None:
        rows = client.citing_opinions(cluster_id, limit=50)
        for r in rows or []:
            scanned += 1
            found = scan_context(r.get("snippet") or "", [], require_mention=False, limit=1)
            if found:
                out.append(f"{found[0].label} by {r.get('case_name') or 'a citing opinion'}: “{found[0].snippet[:220]}”")
    return list(dict.fromkeys(out)), scanned


def gate_good_law(
    opinion_id: int | None,
    session: Session,
    client: CourtListenerClient | None = None,
    cluster_id: int | None = None,
) -> GateResult:
    if opinion_id is None and cluster_id is None:
        return GateResult(gate=4, name="good_law", outcome="skip", detail="no record to check for later treatment")
    findings, scanned = good_law_findings(opinion_id, session, client, cluster_id)
    if findings:
        shown = [f if len(f) <= 260 else f[:257].rsplit(" ", 1)[0] + "…" for f in findings[:3]]
        more = f" (+{len(findings) - 3} more)" if len(findings) > 3 else ""
        return GateResult(gate=4, name="good_law", outcome="warn", detail="; ".join(shown) + more)
    return GateResult(gate=4, name="good_law", outcome="pass", detail=f"no negative treatment found ({scanned} citing opinions scanned)")
