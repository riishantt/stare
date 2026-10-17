from __future__ import annotations

import bz2
import shutil
from pathlib import Path

import pytest
from sqlalchemy import select

from stare.db.models import Citation, CitationEdge, Opinion
from stare.ingest.courtlistener_bulk import (
    find_files,
    html_to_text,
    import_courtlistener_bulk,
    iter_rows,
    opinion_text,
)
from stare.ingest.pipeline import load_courts

FIX = Path(__file__).parent / "fixtures" / "cl_bulk"


def test_find_files():
    found = find_files(FIX)
    assert set(found) == {"courts", "dockets", "clusters", "citations", "opinions", "citation_map"}
    assert found["clusters"].name.startswith("opinion-clusters")
    assert found["citation_map"].name.startswith("citation-map")


def test_iter_rows_streams_multiline_fields():
    rows = list(iter_rows(find_files(FIX)["opinions"]))
    assert rows[0]["id"] == "100" and "\n\n" in rows[0]["plain_text"]
    assert len(rows) == 6


def test_iter_rows_reads_bz2(tmp_path):
    src = find_files(FIX)["dockets"]
    dst = tmp_path / "dockets-x.csv.bz2"
    dst.write_bytes(bz2.compress(src.read_bytes()))
    assert [r["id"] for r in iter_rows(dst)] == ["1", "2", "3", "4", "5"]


def test_opinion_text_prefers_plain_then_html():
    assert opinion_text({"plain_text": "plain", "html": "<p>x</p>"}) == "plain"
    assert opinion_text({"plain_text": "", "html_with_citations": "<p>Hello <i>there</i></p>"}).replace("\n", " ").startswith("Hello")
    assert opinion_text({}) == ""
    assert "x" in html_to_text("<div><p>x</p></div>")


def test_import_filters_federal_courts_and_employment_text(session):
    load_courts(session)
    counts = import_courtlistener_bulk(FIX, session=session)
    ops = {o.source_id: o for o in session.scalars(select(Opinion))}
    assert counts["opinions"] == len(ops)
    assert set(ops) == {"10", "11", "13"}  # 12 is a Texas state court; 14 has no employment hits; 101 is a contract case
    a = ops["10"]
    assert a.court_id == "ca5" and a.published is True and a.year == 2019
    assert a.citation == "900 F.3d 100" and a.docket_number == "No. 19-10001"
    assert a.source == "courtlistener_bulk"
    assert ops["11"].published is False and ops["11"].court_id == "txnd"
    assert "Title VII" in ops["11"].plain_text  # html-only opinion converted to text
    cites = {(c.reporter, c.cite_type) for c in session.scalars(select(Citation).where(Citation.opinion_id == a.id))}
    assert cites == {("F.3d", "official")}  # the Westlaw cite (type 7) is dropped
    assert ops["11"].citation == "200 F. App'x 300"


def test_citation_map_builds_edges_between_imported_only(session):
    load_courts(session)
    counts = import_courtlistener_bulk(FIX, session=session)
    edges = session.scalars(select(CitationEdge)).all()
    assert counts["edges"] == len(edges) == 2
    ids = {o.source_id: o.id for o in session.scalars(select(Opinion))}
    assert {(e.citing_id, e.cited_id) for e in edges} == {(ids["13"], ids["10"]), (ids["11"], ids["10"])}


def test_import_is_idempotent_and_limit(session):
    load_courts(session)
    import_courtlistener_bulk(FIX, session=session, limit=1)
    assert len(session.scalars(select(Opinion)).all()) == 1
    import_courtlistener_bulk(FIX, session=session)
    import_courtlistener_bulk(FIX, session=session)
    assert len(session.scalars(select(Opinion)).all()) == 3


def test_court_restriction_and_no_filter(session):
    load_courts(session)
    import_courtlistener_bulk(FIX, session=session, courts={"txnd"}, employment_only=False)
    assert {o.court_id for o in session.scalars(select(Opinion))} == {"txnd"}


def test_missing_files_raise(session, tmp_path):
    shutil.copy(FIX / "courts-2024-01-01.csv", tmp_path)
    with pytest.raises(FileNotFoundError):
        import_courtlistener_bulk(tmp_path, session=session)


def test_monthly_refresh_imports_bulk_rebuilds_chunks_and_stamps(session, settings):
    import json

    from stare.db.models import Chunk
    from stare.ingest.pipeline import refresh_corpus

    counts = refresh_corpus(session, bulk_dir=FIX, online=False)
    ops = {o.source_id for o in session.scalars(select(Opinion))}
    assert {"10", "11", "13"} <= ops and counts["opinions"] == len(ops) > 3  # bulk cases plus the cached seed
    assert counts["chunks"] == len(session.scalars(select(Chunk)).all()) > 0
    stamp = json.loads((settings.data_dir / "refresh.json").read_text())
    assert stamp["after"] == counts and stamp["online"] is False and stamp["refreshed_at"]
    assert refresh_corpus(session, bulk_dir=FIX, online=False)["opinions"] == counts["opinions"]  # idempotent
