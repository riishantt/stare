from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from stare.db.models import Chunk, StatuteSection
from stare.ingest.pipeline import rebuild_chunks
from stare.ingest.statutes import import_statutes, parse_ecfr_xml, parse_usc_html

FIX = Path(__file__).parent / "fixtures"


def test_parse_usc_section():
    heading, text = parse_usc_html((FIX / "usc-42-2000e-3.html").read_text())
    assert heading == "Other unlawful employment practices"
    assert text.startswith("(a) Discrimination for making charges")
    assert "It shall be an unlawful employment practice for an employer to discriminate" in text
    assert "(b) Printing or publication of notices" in text
    assert "<" not in text and "  " not in text


def test_parse_ecfr_sections_and_appendix():
    secs = parse_ecfr_xml((FIX / "ecfr_mini.xml").read_text(), title=29, part="1630", statute="ada")
    assert [s.citation for s in secs] == ["29 C.F.R. § 1630.1", "29 C.F.R. § 1630.2", "29 C.F.R. pt. 1630, app."]
    first = secs[0]
    assert first.heading == "Purpose, applicability, and construction"
    assert first.text.startswith("(a) Purpose. The purpose of this part")
    assert "56 FR" not in first.text  # credit line dropped
    assert all(s.statute == "ada" and s.code == "CFR" and s.title == 29 for s in secs)


def test_import_from_raw_cache_is_offline_and_idempotent(session, tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "usc-42-2000e-3.html").write_text((FIX / "usc-42-2000e-3.html").read_text())
    (raw / "cfr-29-1630.xml").write_text((FIX / "ecfr_mini.xml").read_text())
    assert import_statutes(session, offline=True, raw_dir=raw) == 4
    assert import_statutes(session, offline=True, raw_dir=raw) == 4
    rows = {r.citation: r for r in session.scalars(select(StatuteSection))}
    assert len(rows) == 4
    t7 = rows["42 U.S.C. § 2000e-3"]
    assert (t7.code, t7.title, t7.section, t7.statute) == ("USC", 42, "2000e-3", "title_vii")
    assert rows["29 C.F.R. § 1630.2"].statute == "ada" and rows["29 C.F.R. § 1630.2"].source == "ecfr"


def test_statute_chunks_carry_citation_prefix(session, tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "usc-42-2000e-3.html").write_text((FIX / "usc-42-2000e-3.html").read_text())
    import_statutes(session, offline=True, raw_dir=raw)
    assert rebuild_chunks(session) >= 1
    chunk = session.scalars(select(Chunk)).first()
    assert chunk.kind == "statute" and chunk.section_id and chunk.embedding is None
    assert chunk.text.startswith("42 U.S.C. § 2000e-3 Other unlawful employment practices\n")
