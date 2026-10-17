"""Streaming importer for CourtListener bulk CSV exports (courts, dockets, clusters, citations, opinions,
citation map), filtered to federal employment-discrimination opinions.

Heavy path, never run on the laptop by default. No file is loaded into memory: the small id-joins are staged in
a temporary SQLite file, and opinions (the large file) are streamed row by row.
"""

from __future__ import annotations

import bz2
import contextlib
import csv
import gzip
import re
import sqlite3
import sys
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from stare.courts.hierarchy import CourtHierarchy
from stare.db.models import Citation, CitationEdge, CourtRow, Opinion
from stare.ingest.cap import parse_cite
from stare.ingest.relevance import is_employment_text

_KINDS = (  # (kind, filename substrings); first match wins
    ("citation_map", ("citation-map", "citation_map", "opinionscited", "opinions_cited")),
    ("clusters", ("opinion-cluster", "opinioncluster", "opinion_cluster", "clusters")),
    ("dockets", ("docket",)),
    ("citations", ("citations", "search_citation")),
    ("courts", ("courts",)),
    ("opinions", ("opinions", "search_opinion")),
)
_TEXT_COLS = ("plain_text", "html_with_citations", "html", "html_lawbox", "html_columbia", "html_anon_2020", "xml_harvard")
_SKIP_CITE_TYPES = {"6", "7"}  # lexis, west (WL) cites are vendor citations
_FED_COURTS_LEVELS = {"supreme", "appellate", "district"}


def find_files(directory: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for f in sorted(Path(directory).iterdir()):
        name = f.name.lower()
        if not re.search(r"\.csv(\.bz2|\.gz)?$", name):
            continue
        for kind, keys in _KINDS:
            if any(k in name for k in keys):
                found.setdefault(kind, f)
                break
    return found


def open_text(path: Path):
    p = str(path)
    if p.endswith(".bz2"):
        return bz2.open(p, "rt", encoding="utf-8", newline="")
    if p.endswith(".gz"):
        return gzip.open(p, "rt", encoding="utf-8", newline="")
    return open(p, encoding="utf-8", newline="")


def iter_rows(path: Path) -> Iterator[dict[str, str]]:
    """Stream CSV rows as dicts (CourtListener exports use quote=` and escape=\\ conventions)."""
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    with open_text(path) as fh:
        yield from csv.DictReader(fh, quotechar='"', escapechar="\\", doublequote=True)


def html_to_text(raw: str) -> str:
    return re.sub(r"[ \t]+\n", "\n", BeautifulSoup(raw, "lxml").get_text("\n")).strip()


def opinion_text(row: dict[str, str]) -> str:
    for col in _TEXT_COLS:
        v = (row.get(col) or "").strip()
        if v:
            return v if col == "plain_text" else html_to_text(v)
    return ""


def _stage_db(tmpdir: Path) -> sqlite3.Connection:
    con = sqlite3.connect(tmpdir / "stage.sqlite")
    con.executescript(
        """
        CREATE TABLE dockets(id TEXT PRIMARY KEY, court_id TEXT, docket_number TEXT);
        CREATE TABLE clusters(id TEXT PRIMARY KEY, docket_id TEXT, date_filed TEXT, case_name TEXT,
                              case_name_full TEXT, published INTEGER);
        CREATE TABLE cites(cluster_id TEXT, volume TEXT, reporter TEXT, page TEXT, type TEXT);
        CREATE INDEX cites_ix ON cites(cluster_id);
        CREATE TABLE imported(op_id TEXT PRIMARY KEY, cluster_id TEXT);
        """
    )
    return con


def _preferred(cites: list[tuple[str, str, str]]) -> int:
    for i, (_, rep, _) in enumerate(cites):
        if rep == "U.S.":
            return i
    return 0


def import_courtlistener_bulk(
    directory: Path,
    *,
    session: Session,
    courts: set[str] | None = None,
    employment_only: bool = True,
    limit: int | None = None,
    batch: int = 500,
    say: Callable[[str], None] = lambda s: None,
) -> dict[str, int]:
    """Import employment opinions from a directory of CourtListener bulk CSVs. Returns counts."""
    files = find_files(Path(directory))
    missing = {"dockets", "clusters", "opinions"} - files.keys()
    if missing:
        raise FileNotFoundError(f"missing bulk files in {directory}: {sorted(missing)}")
    hierarchy = CourtHierarchy.default()
    wanted = {c.id for c in hierarchy.all() if c.level in _FED_COURTS_LEVELS}
    if courts:
        wanted &= set(courts)
    counts = {"dockets": 0, "clusters": 0, "citations": 0, "opinions": 0, "edges": 0}

    with tempfile.TemporaryDirectory(prefix="stare-clbulk-") as tmp, contextlib.closing(_stage_db(Path(tmp))) as con:
        for r in iter_rows(files["dockets"]):
            if r.get("court_id") in wanted:
                con.execute("INSERT OR IGNORE INTO dockets VALUES (?,?,?)", (r["id"], r["court_id"], r.get("docket_number", "")))
                counts["dockets"] += 1
        con.commit()
        say(f"dockets staged: {counts['dockets']}")
        for r in iter_rows(files["clusters"]):
            if con.execute("SELECT 1 FROM dockets WHERE id=?", (r.get("docket_id"),)).fetchone():
                con.execute(
                    "INSERT OR IGNORE INTO clusters VALUES (?,?,?,?,?,?)",
                    (r["id"], r["docket_id"], r.get("date_filed") or None, r.get("case_name") or r.get("case_name_short", ""),
                     r.get("case_name_full", ""), int((r.get("precedential_status") or "").lower() == "published")),
                )
                counts["clusters"] += 1
        con.commit()
        say(f"clusters staged: {counts['clusters']}")
        if "citations" in files:
            for r in iter_rows(files["citations"]):
                if r.get("type") in _SKIP_CITE_TYPES:
                    continue
                if con.execute("SELECT 1 FROM clusters WHERE id=?", (r.get("cluster_id"),)).fetchone():
                    con.execute("INSERT INTO cites VALUES (?,?,?,?,?)", (r["cluster_id"], r["volume"], r["reporter"], r["page"], r.get("type", "")))
                    counts["citations"] += 1
            con.commit()

        n = 0
        for r in iter_rows(files["opinions"]):
            cl = con.execute(
                "SELECT c.id, c.date_filed, c.case_name, c.case_name_full, c.published, d.court_id, d.docket_number "
                "FROM clusters c JOIN dockets d ON d.id=c.docket_id WHERE c.id=?", (r.get("cluster_id"),),
            ).fetchone()
            if not cl:
                continue
            text = opinion_text(r)
            if not text or (employment_only and not is_employment_text(text)):
                continue
            cid, date_filed, name, name_full, published, court_id, docket_number = cl
            if session.scalar(select(Opinion.id).where(Opinion.source == "courtlistener_bulk", Opinion.source_id == cid)):
                con.execute("INSERT OR IGNORE INTO imported VALUES (?,?)", (r["id"], cid))
                continue
            cites = con.execute("SELECT volume, reporter, page FROM cites WHERE cluster_id=?", (cid,)).fetchall()
            norm = []
            for v, rep, pg in cites:
                p = parse_cite(f"{v} {rep} {pg}")
                if p and p not in norm:
                    norm.append(p)
            pref = norm[_preferred([(v, rp, g) for v, rp, g in norm])] if norm else None
            op = Opinion(
                court_id=court_id if session.get(CourtRow, court_id) else None,
                case_name=name or "", case_name_full=name_full or "",
                citation=" ".join(pref) if pref else "", date_filed=date_filed,
                year=int(date_filed[:4]) if date_filed and date_filed[:4].isdigit() else None,
                docket_number=docket_number or "", published=bool(published), plain_text=text,
                source="courtlistener_bulk", source_id=cid, url=f"https://www.courtlistener.com/?q=cluster_id%3A{cid}",
            )
            session.add(op)
            session.flush()
            for p in norm:
                session.add(Citation(opinion_id=op.id, volume=p[0], reporter=p[1], page=p[2], cite=" ".join(p),
                                     cite_type="official" if p == pref else "parallel"))
            con.execute("INSERT OR IGNORE INTO imported VALUES (?,?)", (r["id"], cid))
            n += 1
            if n % batch == 0:
                session.commit()
            if limit and n >= limit:
                break
        session.commit()
        counts["opinions"] = n
        say(f"opinions imported: {n}")

        if "citation_map" in files and n:
            m = 0
            for r in iter_rows(files["citation_map"]):
                a = con.execute("SELECT cluster_id FROM imported WHERE op_id=?", (r.get("citing_opinion_id"),)).fetchone()
                b = con.execute("SELECT cluster_id FROM imported WHERE op_id=?", (r.get("cited_opinion_id"),)).fetchone()
                if not a or not b or a[0] == b[0]:
                    continue
                citing = session.scalar(select(Opinion.id).where(Opinion.source == "courtlistener_bulk", Opinion.source_id == a[0]))
                cited = session.scalar(select(Opinion.id).where(Opinion.source == "courtlistener_bulk", Opinion.source_id == b[0]))
                if citing and cited and not session.scalar(
                    select(CitationEdge.id).where(CitationEdge.citing_id == citing, CitationEdge.cited_id == cited)
                ):
                    session.add(CitationEdge(citing_id=citing, cited_id=cited))
                    m += 1
                    if m % batch == 0:
                        session.commit()
            session.commit()
            counts["edges"] = m
    return counts
