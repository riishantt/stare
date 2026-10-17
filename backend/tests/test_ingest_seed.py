from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from stare.db.models import Chunk, Citation, CitationEdge, Opinion, StatuteSection, Treatment
from stare.ingest.pipeline import build_corpus, corpus_counts, load_courts, rebuild_chunks
from stare.ingest.seed import SEED_DIR, build_seed, load_manifest, raw_name

FIX = Path(__file__).parent / "fixtures" / "seed_mini"


def _build(session):
    load_courts(session)
    return build_seed(session, offline=True, manifest_path=FIX / "manifest.json", raw_dir=FIX / "raw",
                      treatments_path=FIX / "treatments.json")


def test_seed_build_offline_from_fixture(session):
    result = _build(session)
    assert result == {"opinions": 3, "edges": 2, "treatments": 1}
    assert session.scalars(select(Opinion)).all().__len__() == 3
    assert session.scalars(select(CitationEdge)).all().__len__() == 2


def test_seed_is_idempotent(session):
    _build(session)
    again = _build(session)
    assert again["treatments"] == 0 and again["edges"] == 0
    assert len(session.scalars(select(Opinion)).all()) == 3
    assert len(session.scalars(select(Treatment)).all()) == 1


def test_treatment_attached_by_citation(session):
    _build(session)
    t = session.scalars(select(Treatment)).one()
    op = session.get(Opinion, t.opinion_id)
    assert op.citation == "100 F.3d 1"
    assert t.kind == "abrogated" and t.severity == "negative" and t.source == "curated"


def test_extra_cites_are_added_and_preferred(session):
    _build(session)
    op = session.scalar(select(Opinion).where(Opinion.source_id == "333"))
    assert op.citation == "500 U.S. 5"
    assert {c.cite for c in session.scalars(select(Citation).where(Citation.opinion_id == op.id))} == {
        "120 F. App'x 300", "500 U.S. 5"}


def test_needs_token_entries_are_skipped(session):
    _build(session)
    assert not session.scalars(select(Opinion).where(Opinion.citation == "678 F. Supp. 3d 443")).all()


def test_rebuild_chunks_for_seed(session):
    _build(session)
    n = rebuild_chunks(session)
    chunks = session.scalars(select(Chunk)).all()
    assert n == len(chunks) >= 3
    assert all(c.kind == "opinion" and c.embedding is None for c in chunks)
    assert rebuild_chunks(session) == n  # rebuild replaces rather than appends


def test_corpus_counts(session):
    _build(session)
    rebuild_chunks(session)
    counts = corpus_counts(session)
    assert counts["opinions"] == 3 and counts["edges"] == 2 and counts["treatments"] == 1
    assert counts["courts"] > 100 and counts["statute_sections"] == 0


# ---- the committed seed corpus ------------------------------------------------------------------


def test_committed_manifest_is_consistent():
    manifest = load_manifest()
    seen = set()
    for e in manifest["cases"]:
        assert e["cite"] not in seen
        seen.add(e["cite"])
        if e["status"] == "ok":
            assert (SEED_DIR / "raw" / raw_name(e)).exists(), e["cite"]
        else:
            assert e["status"] in {"needs_token", "not_found"}
    assert sum(e["status"] == "ok" for e in manifest["cases"]) >= 80


def test_committed_seed_builds_offline(session):
    load_courts(session)
    result = build_seed(session, offline=True)
    assert result["opinions"] >= 80 and result["edges"] > 20 and result["treatments"] >= 6
    cites = {c.cite for c in session.scalars(select(Citation))}
    for c in ("411 U.S. 792", "548 U.S. 53", "534 U.S. 184", "104 F.3d 702", "575 U.S. 206", "590 U.S. 644",
              "600 U.S. 447", "601 U.S. 346", "905 F. Supp. 2d 121"):
        assert c in cites
    mattern = session.scalar(select(Opinion).where(Opinion.citation == "104 F.3d 702"))
    assert mattern.court_id == "ca5"
    toyota = session.scalar(select(Opinion).where(Opinion.citation == "534 U.S. 184"))
    assert any("Pub. L. 110-325" in t.by for t in session.scalars(select(Treatment).where(Treatment.opinion_id == toyota.id)))


def test_build_corpus_offline_end_to_end(session):
    counts = build_corpus(session, offline_only=True)
    assert counts["opinions"] >= 80 and counts["statute_sections"] >= 100 and counts["chunks"] > counts["opinions"]
    assert session.scalars(select(StatuteSection).where(StatuteSection.citation == "42 U.S.C. § 2000e-3")).one()
