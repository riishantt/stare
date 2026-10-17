"""Caselaw Access Project (static.case.law) fetcher and importer."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
from eyecite import get_citations
from sqlalchemy import select
from sqlalchemy.orm import Session

from stare.text import mark_separate_opinions, part_marker, strip_syllabus
from stare.courts.hierarchy import CourtHierarchy
from stare.db.models import Citation, CitationEdge, CourtRow, Opinion

CAP_BASE = "https://static.case.law"
USER_AGENT = "STARE-capstone/0.1 (academic research; free public data)"
_last_request = 0.0


def parse_cite(cite: str) -> tuple[str, str, str] | None:
    """'401 U. S. 424' -> ('401', 'U.S.', '424'); None for vendor/unparseable cites."""
    for c in get_citations(cite):
        g = getattr(c, "groups", None) or {}
        if g.get("volume") and g.get("reporter") and g.get("page") and not re.search(r"LEXIS|WL|SCDB", g["reporter"]):
            return g["volume"], c.corrected_reporter(), g["page"]
    return None


def _get(url: str, *, delay: float = 0.3, client: httpx.Client | None = None) -> httpx.Response:
    global _last_request
    wait = delay - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    try:
        if client:
            return client.get(url, timeout=60)
        return httpx.get(url, timeout=60, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    finally:
        _last_request = time.monotonic()


def slim_cap_case(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep only the fields STARE needs (opinion text, cites, court, dates) to keep the cache small."""
    body = raw.get("casebody") or {}
    return {
        "id": raw["id"],
        "name": raw.get("name", ""),
        "name_abbreviation": raw.get("name_abbreviation", ""),
        "decision_date": raw.get("decision_date"),
        "docket_number": raw.get("docket_number", ""),
        "first_page": raw.get("first_page"),
        "last_page": raw.get("last_page"),
        "citations": raw.get("citations", []),
        "court": raw.get("court", {}),
        "cites_to": [
            {k: c.get(k) for k in ("cite", "reporter", "case_ids", "case_paths", "year", "opinion_index")}
            for c in raw.get("cites_to", [])
            if c.get("case_ids")
        ],
        "casebody": {
            "opinions": [
                {"type": o.get("type", ""), "author": o.get("author"), "text": o.get("text", "")}
                for o in body.get("opinions", [])
            ]
        },
    }


def fetch_cap_case(reporter_slug: str, volume: int | str, page: int | str, *, expect_name: str | None = None,
                   client: httpx.Client | None = None) -> dict | None:
    """Fetch one case JSON from static.case.law. Tries page-01, then the volume's CasesMetadata.json.

    When `expect_name` is given (a distinctive party-name fragment), only a case whose name matches is accepted.
    """
    vol, pg = int(volume), int(page)
    base = f"{CAP_BASE}/{reporter_slug}/{vol}"

    def ok(case: dict) -> bool:
        if not expect_name:
            return True
        hay = f"{case.get('name_abbreviation', '')} {case.get('name', '')}".lower()
        return _norm_name(expect_name) in _norm_name(hay)

    for n in (1, 2, 3):
        r = _get(f"{base}/cases/{pg:04d}-{n:02d}.json", client=client)
        if r.status_code == 200:
            case = r.json()
            if ok(case):
                return case
        elif r.status_code != 404:
            return None
    r = _get(f"{base}/CasesMetadata.json", client=client)
    if r.status_code != 200:
        return None
    for meta in r.json():
        if str(meta.get("first_page")) == str(pg) and ok(meta):
            rc = _get(f"{base}/cases/{meta['file_name']}.json", client=client)
            if rc.status_code == 200:
                return rc.json()
    return None


def _norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower().replace("&", " and ")).strip()


def _court_id(case: dict, hierarchy: CourtHierarchy) -> str | None:
    # Only the Supreme Court is reported in U.S. Reports / S. Ct. / L. Ed.; CAP's court field is sometimes
    # the lower court for these volumes, so the reporter decides.
    if any(re.match(r"\d+\s+(?:U\.\s?S\.|S\.\s?Ct\.|L\.\s?Ed)", c.get("cite", "")) for c in case.get("citations", [])
           if c.get("type") == "official"):
        return "scotus"
    court = case.get("court") or {}
    return hierarchy.normalize(court.get("name_abbreviation", "")) or hierarchy.normalize(court.get("name", ""))


def _is_published(cites: list[dict]) -> bool:
    return not any("App'x" in c.get("cite", "") or "Fed. Appx" in c.get("cite", "") for c in cites)


def _year(d: str | None) -> int | None:
    try:
        return int((d or "")[:4])
    except ValueError:
        return None


def case_text(case: dict) -> str:
    """Opinion of the court first; every separate opinion is introduced by a marker line (stare.text.part_marker)."""
    ops = [o for o in case["casebody"]["opinions"] if o.get("text")]
    ops.sort(key=lambda o: o.get("type") != "majority")
    parts = []
    for o in ops:
        body = mark_separate_opinions(strip_syllabus(o["text"].strip()))
        parts.append(body if o.get("type") == "majority" else f"{part_marker(o.get('type', ''), o.get('author'))}\n{body}")
    return "\n\n".join(parts)


def import_cap_case(session: Session, case: dict, *, hierarchy: CourtHierarchy | None = None,
                    source: str = "cap") -> Opinion:
    """Create (or return the existing) Opinion plus Citation rows for the official and parallel cites."""
    h = hierarchy or CourtHierarchy.default()
    sid = str(case["id"])
    existing = session.scalar(select(Opinion).where(Opinion.source == source, Opinion.source_id == sid))
    if existing:
        return existing
    cites = case.get("citations", [])
    parsed = [(c, parse_cite(c["cite"])) for c in cites if c.get("type") != "vendor"]
    parsed = [(c, p) for c, p in parsed if p]
    official = next((c["cite"] for c, _ in parsed if c.get("type") == "official"), None)
    preferred = official or (parsed[0][0]["cite"] if parsed else (cites[0]["cite"] if cites else ""))
    cid = _court_id(case, h)
    if cid and not session.get(CourtRow, cid):
        cid = None
    first = parsed[0][1] if parsed else None
    op = Opinion(
        court_id=cid,
        case_name=case.get("name_abbreviation") or case.get("name", ""),
        case_name_full=case.get("name", ""),
        citation=preferred,
        date_filed=case.get("decision_date"),
        year=_year(case.get("decision_date")),
        docket_number=case.get("docket_number", ""),
        published=_is_published(cites),
        plain_text=case_text(case),
        source=source,
        source_id=sid,
        url=f"https://case.law/caselaw/?reporter={first[1]}&volume={first[0]}&case={first[2]}" if first else None,
    )
    session.add(op)
    session.flush()
    seen: set[tuple[str, str, str]] = set()
    for c, p in parsed:
        if p in seen:
            continue
        seen.add(p)
        session.add(Citation(opinion_id=op.id, volume=p[0], reporter=p[1], page=p[2],
                             cite=f"{p[0]} {p[1]} {p[2]}", cite_type=c.get("type", "parallel")))
    session.flush()
    return op


def _cite_context(text: str, cite: str, width: int = 300) -> str:
    """Window of text around the first occurrence of `cite` (whitespace/dots tolerant)."""
    parts = re.split(r"[\s.]+", cite.strip())
    pat = r"[\s.]*".join(re.escape(p) for p in parts if p)
    m = re.search(pat, text)
    if not m:
        return ""
    seg = text[max(0, m.start() - width) : min(len(text), m.end() + width // 2)]
    return re.sub(r"\s+", " ", seg).strip()


def link_cap_edges(session: Session, case: dict, *, source: str = "cap") -> int:
    """Create CitationEdge rows from this case to every cited case already in the DB. Returns edges added."""
    citing = session.scalar(select(Opinion).where(Opinion.source == source, Opinion.source_id == str(case["id"])))
    if not citing:
        return 0
    text = case_text(case)
    added = 0
    for c in case.get("cites_to", []):
        for cid in c.get("case_ids") or []:
            cited = session.scalar(select(Opinion).where(Opinion.source == "cap", Opinion.source_id == str(cid)))
            if not cited or cited.id == citing.id:
                continue
            if session.scalar(select(CitationEdge.id).where(CitationEdge.citing_id == citing.id,
                                                             CitationEdge.cited_id == cited.id)):
                continue
            session.add(CitationEdge(citing_id=citing.id, cited_id=cited.id, context=_cite_context(text, c["cite"])))
            added += 1
    session.flush()
    return added


def iter_cap_volume(path: Path) -> Iterator[dict]:
    """Yield case JSON dicts from a downloaded reporter-volume directory (`.../cases/*.json`)."""
    path = Path(path)
    cases = path / "cases" if (path / "cases").is_dir() else path
    for f in sorted(cases.glob("*.json")):
        try:
            yield json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue


def import_cap_bulk(path: Path, *, session: Session | None = None, limit: int | None = None,
                    employment_only: bool = True, batch: int = 200) -> int:
    """Import a downloaded reporter volume (or a directory of volumes). Heavy path; not run by default."""
    from stare.db import session_scope
    from stare.ingest.relevance import is_employment_text

    root = Path(path)
    dirs = [root] if (root / "cases").is_dir() or any(root.glob("*.json")) else sorted(
        p for p in root.rglob("cases") if p.is_dir()
    )
    n = 0

    def run(s: Session) -> None:
        nonlocal n
        for d in dirs:
            for case in iter_cap_volume(d):
                if not case.get("casebody") or (employment_only and not is_employment_text(case_text(case))):
                    continue
                import_cap_case(s, slim_cap_case(case))
                n += 1
                if n % batch == 0:
                    s.commit()
                if limit and n >= limit:
                    return

    if session is not None:
        run(session)
    else:
        with session_scope() as s:
            run(s)
    return n
