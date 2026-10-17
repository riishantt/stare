"""Seed corpus: a curated manifest of real employment-discrimination cases, cached as raw JSON.

`data/seed/manifest.json` lists the cases; `data/seed/raw/` holds the fetched, slimmed JSON (committed, so a
fresh clone builds offline); `data/seed/treatments.json` holds curated negative-treatment facts.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from stare.config import REPO_DIR
from stare.courts.hierarchy import CourtHierarchy
from stare.db.models import Citation, Opinion, Treatment
from stare.ingest.cap import (
    USER_AGENT,
    fetch_cap_case,
    import_cap_case,
    link_cap_edges,
    parse_cite,
    slim_cap_case,
)

SEED_DIR = REPO_DIR / "data" / "seed"


def raw_name(entry: dict) -> str:
    return f"{entry['reporter']}-{entry['volume']}-{int(entry['page']):04d}.json"


def load_manifest(path: Path | None = None) -> dict:
    return json.loads((path or SEED_DIR / "manifest.json").read_text())


def save_manifest(manifest: dict, path: Path | None = None) -> None:
    (path or SEED_DIR / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")


def fetch_lii_supreme_court(docket: str, *, name: str, cite: str) -> dict | None:
    """Fetch a recent Supreme Court opinion (post-CAP coverage) from law.cornell.edu as a CAP-shaped dict."""
    r = httpx.get(f"https://www.law.cornell.edu/supremecourt/text/{docket}", timeout=60, follow_redirects=True,
                  headers={"User-Agent": USER_AGENT})
    if r.status_code != 200:
        return None
    content = BeautifulSoup(r.text, "lxml").select_one("#content")
    if content is None:
        return None
    paras = [re.sub(r"\s+", " ", p.get_text(" ")).strip() for p in content.find_all(["p", "h2", "h3", "blockquote"])]
    text = "\n\n".join(re.sub(r" ([,.;:)])", r"\1", re.sub(r"\( ", "(", t)) for t in paras if t)
    m = re.search(r"Decided\W+([A-Z][a-z]+ \d{1,2}, \d{4})", re.sub(r"\s+", " ", content.get_text(" ")))
    if not m or len(text) < 5000:
        return None
    decided = datetime.strptime(m.group(1), "%B %d, %Y").date().isoformat()
    return {
        "id": f"lii-{docket}", "name": name, "name_abbreviation": name, "decision_date": decided,
        "docket_number": f"No. {docket}", "citations": [{"type": "official", "cite": cite}],
        "court": {"name_abbreviation": "U.S.", "name": "Supreme Court of the United States"},
        "cites_to": [], "casebody": {"opinions": [{"type": "majority", "author": None, "text": text}]},
    }


def fetch_manifest(manifest: dict, raw_dir: Path | None = None, *, refetch: bool = False,
                   say: Callable[[str], None] = lambda s: None) -> dict:
    """Fetch every manifest case not yet cached from CAP static; updates each entry's `status`."""
    raw_dir = raw_dir or SEED_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for e in manifest["cases"]:
        f = raw_dir / raw_name(e)
        if f.exists() and not refetch:
            e["status"] = "ok"
            continue
        if e.get("status") == "needs_token":
            continue
        if e.get("source") == "lii":
            case = fetch_lii_supreme_court(e["lii_docket"], name=e["name"], cite=e["cite"])
            if case:
                f.write_text(json.dumps(case, ensure_ascii=False))
            e["status"] = "ok" if case else "not_found"
            say(f"{'ok  ' if case else 'MISS'} {e['cite']} {e['name']}")
            continue
        case = fetch_cap_case(e["reporter"], e["volume"], e["page"], expect_name=e.get("match") or e["name"])
        if case is None:
            e["status"] = "not_found"
            say(f"MISS {e['cite']} {e['name']}")
            continue
        f.write_text(json.dumps(slim_cap_case(case), ensure_ascii=False))
        e["status"] = "ok"
        say(f"ok   {e['cite']} {case.get('name_abbreviation')}")
    return manifest


def load_treatments(session: Session, treatments_path: Path | None = None) -> int:
    path = treatments_path or SEED_DIR / "treatments.json"
    if not path.exists():
        return 0
    added = 0
    for t in json.loads(path.read_text())["treatments"]:
        p = parse_cite(t["cite"])
        if not p:
            continue
        op_id = session.scalar(
            select(Citation.opinion_id).where(Citation.volume == p[0], Citation.reporter == p[1], Citation.page == p[2])
        )
        if op_id is None:
            continue
        if session.scalar(select(Treatment.id).where(Treatment.opinion_id == op_id, Treatment.kind == t["kind"],
                                                     Treatment.by == t["by"])):
            continue
        session.add(Treatment(opinion_id=op_id, kind=t["kind"], by=t["by"], note=t.get("note", ""),
                              severity=t.get("severity", "warning"), source="curated"))
        added += 1
    session.flush()
    return added


def _add_extra_cites(session: Session, op: Opinion, extras: list[dict]) -> None:
    """Add parallel/official reporter cites that CAP lacks (e.g. U.S. Reports cites for post-2014 S. Ct. cases)."""
    for x in extras:
        p = parse_cite(x["cite"])
        if not p or session.scalar(select(Citation.id).where(Citation.opinion_id == op.id, Citation.volume == p[0],
                                                              Citation.reporter == p[1], Citation.page == p[2])):
            continue
        session.add(Citation(opinion_id=op.id, volume=p[0], reporter=p[1], page=p[2], cite=" ".join(p),
                             cite_type=x.get("type", "parallel")))
        if x.get("type") == "official":
            op.citation = " ".join(p)
    session.flush()


def build_seed(session: Session, *, offline: bool = True, manifest_path: Path | None = None,
               raw_dir: Path | None = None, treatments_path: Path | None = None,
               say: Callable[[str], None] = lambda s: None) -> dict[str, int]:
    """Import all cached seed cases (fetching missing ones first when online), edges and treatments."""
    manifest = load_manifest(manifest_path)
    raw_dir = raw_dir or SEED_DIR / "raw"
    if not offline:
        fetch_manifest(manifest, raw_dir, say=say)
        save_manifest(manifest, manifest_path)
    h = CourtHierarchy.default()
    cases = []
    for e in manifest["cases"]:
        f = raw_dir / raw_name(e)
        if f.exists():
            cases.append((e, json.loads(f.read_text())))
    for e, case in cases:
        op = import_cap_case(session, case, hierarchy=h, source=e.get("source") or "cap")
        if e.get("published") is not None:
            op.published = bool(e["published"])
        _add_extra_cites(session, op, e.get("extra_cites", []))
    edges = sum(link_cap_edges(session, case, source=e.get("source") or "cap") for e, case in cases)
    treatments = load_treatments(session, treatments_path)
    session.commit()
    return {"opinions": len(cases), "edges": edges, "treatments": treatments}
