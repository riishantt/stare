from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from stare.db.models import Citation, CitationEdge, CourtRow, Opinion
from stare.ingest.cap import (
    import_cap_bulk,
    import_cap_case,
    iter_cap_volume,
    link_cap_edges,
    parse_cite,
    slim_cap_case,
)
from stare.ingest.pipeline import load_courts

FIX = Path(__file__).parent / "fixtures" / "seed_mini" / "raw"


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.mark.parametrize(
    "cite,expected",
    [
        ("401 U. S. 424", ("401", "U.S.", "424")),
        ("104 F.3d 702", ("104", "F.3d", "702")),
        ("678 F. Supp. 3d 443", ("678", "F. Supp. 3d", "443")),
        ("123 F. App'x 456", ("123", "F. App'x", "456")),
        ("1971 U.S. LEXIS 134", None),
        ("SCDB 1970-056", None),
    ],
)
def test_parse_cite(cite, expected):
    assert parse_cite(cite) == expected


def test_import_creates_opinion_and_citations(session):
    load_courts(session)
    op = import_cap_case(session, _load("f3d-100-0001.json"))
    session.commit()
    assert op.case_name == "Alpha v. Beta Corp."
    assert op.court_id == "ca5" and op.published is True and op.year == 1996
    assert op.citation == "100 F.3d 1"
    assert op.source == "cap" and op.source_id == "111"
    assert "ultimate employment decision" in op.plain_text
    cites = {(c.volume, c.reporter, c.page, c.cite_type) for c in session.scalars(select(Citation))}
    assert ("100", "F.3d", "1", "official") in cites
    assert len(cites) == 1 or all(c[1] != "LEXIS" for c in cites)  # vendor cites are skipped


def test_import_is_idempotent(session):
    load_courts(session)
    a = import_cap_case(session, _load("f3d-100-0001.json"))
    b = import_cap_case(session, _load("f3d-100-0001.json"))
    assert a.id == b.id
    assert len(session.scalars(select(Opinion)).all()) == 1


def test_unpublished_and_district_court_mapping(session):
    load_courts(session)
    app = import_cap_case(session, _load("f-appx-120-0300.json"))
    dist = import_cap_case(session, _load("f-supp-2d-50-0077.json"))
    assert app.published is False and app.court_id == "ca9"
    assert dist.published is True and dist.court_id == "txnd"


def test_unknown_court_is_null_not_error(session):
    load_courts(session)
    case = _load("f3d-100-0001.json")
    case["id"] = 5
    case["court"] = {"name_abbreviation": "Moon Ct.", "name": "Moon Court"}
    assert import_cap_case(session, case).court_id is None


def test_edges_only_between_imported_opinions(session):
    load_courts(session)
    cases = [_load(n) for n in ("f3d-100-0001.json", "f-supp-2d-50-0077.json", "f-appx-120-0300.json")]
    for c in cases:
        import_cap_case(session, c)
    added = sum(link_cap_edges(session, c) for c in cases)
    session.commit()
    assert added == 2  # district -> circuit and unpublished -> circuit; 999 is not in the corpus
    edge = session.scalars(select(CitationEdge).join(Opinion, Opinion.id == CitationEdge.citing_id).where(Opinion.source_id == "222")).one()
    assert "Alpha v. Beta Corp., 100 F.3d 1" in edge.context and len(edge.context) < 700
    assert sum(link_cap_edges(session, c) for c in cases) == 0  # idempotent


def test_slim_keeps_only_needed_fields_and_case_cites():
    raw = _load("f-supp-2d-50-0077.json")
    raw["analysis"] = {"big": "x"}
    raw["cites_to"].append({"cite": "42 U.S.C. § 1", "category": "laws:leg_statute"})
    slim = slim_cap_case(raw)
    assert "analysis" not in slim
    assert [c["cite"] for c in slim["cites_to"]] == ["100 F.3d 1", "999 F.3d 9"]
    assert slim["casebody"]["opinions"][0]["text"].startswith("The Court follows")


def test_bulk_volume_directory(session, tmp_path):
    load_courts(session)
    vol = tmp_path / "f3d" / "100"
    (vol / "cases").mkdir(parents=True)
    emp = _load("f3d-100-0001.json")
    emp["casebody"]["opinions"][0]["text"] += " Title VII, 42 U.S.C. § 2000e-2, applies."
    other = {**_load("f-supp-2d-50-0077.json"), "id": 777}
    other["casebody"]["opinions"][0]["text"] = "A contract dispute about widgets."
    (vol / "cases" / "0001-01.json").write_text(json.dumps(emp))
    (vol / "cases" / "0077-01.json").write_text(json.dumps(other))
    assert len(list(iter_cap_volume(vol))) == 2
    n = import_cap_bulk(vol, session=session)
    session.commit()
    assert n == 1
    assert session.scalars(select(Opinion)).one().source_id == "111"
    assert session.get(CourtRow, "ca5")
