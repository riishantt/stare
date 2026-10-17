"""HybridRetriever against a tiny in-test corpus (SQLite, LSA embedder, lexical reranker)."""

from __future__ import annotations

import pytest

from stare.db.models import Chunk, CourtRow, Opinion, StatuteSection
from stare.retrieval.hybrid import HybridRetriever, IndexNotBuiltError, IndexStaleError

OPINIONS = [
    # key, case_name, citation, court, year, [chunks]
    ("mcd", "McDonnell Douglas Corp. v. Green", "411 U.S. 792", "scotus", 1973, [
        "In McDonnell Douglas Corp. v. Green, 411 U.S. 792, the Court held that a Title VII plaintiff must show a prima facie case of discriminatory failure to hire, after which the burden shifts to the employer to articulate a legitimate nondiscriminatory reason.",
        "The employer's reason may be shown to be a pretext for discrimination, and the plaintiff then bears the ultimate burden of persuasion on intentional discrimination.",
    ]),
    ("burl", "Burlington Northern & Santa Fe Railway Co. v. White", "548 U.S. 53", "scotus", 2006, [
        "We hold that the anti-retaliation provision protects an employee from employer actions that would dissuade a reasonable worker from making or supporting a charge of discrimination, even actions outside the workplace.",
        "A materially adverse action in a retaliation claim is one that well might have dissuaded a reasonable worker from complaining about discrimination; reassignment of duties and suspension without pay qualify.",
    ]),
    ("nassar", "University of Texas Southwestern Medical Center v. Nassar", "570 U.S. 338", "scotus", 2013, [
        "Title VII retaliation claims must be proved according to traditional principles of but-for causation, not the lessened motivating-factor causation test.",
    ]),
    ("gross", "Gross v. FBL Financial Services, Inc.", "557 U.S. 167", "scotus", 2009, [
        "An ADEA plaintiff must prove by a preponderance of the evidence that age was the but-for cause of the challenged adverse employment action; the burden of persuasion never shifts to the employer.",
        "The Age Discrimination in Employment Act does not authorize a mixed-motives age discrimination claim, unlike Title VII.",
    ]),
    ("barnett", "US Airways, Inc. v. Barnett", "535 U.S. 391", "scotus", 2002, [
        "Under the ADA a reasonable accommodation such as reassignment to a vacant position may be required, but a seniority system ordinarily defeats the accommodation request.",
    ]),
    ("lowe", "Lowe v. Atlas Logistics", "123 F.3d 456", "ca5", 1998, [
        "The plaintiff in this Fifth Circuit appeal alleged her supervisor fired her after she complained to human resources about sexual harassment; we conclude causal connection was shown by close timing.",
    ]),
]
STATUTES = [
    ("42 U.S.C. § 2000e-3", "USC", 42, "2000e-3", "Other unlawful employment practices", "title_vii",
     "It shall be an unlawful employment practice for an employer to discriminate against any of his employees because he has opposed any practice made an unlawful employment practice by this subchapter, or because he has made a charge, testified, assisted, or participated in an investigation."),
    ("42 U.S.C. § 12112", "USC", 42, "12112", "Discrimination", "ada",
     "No covered entity shall discriminate against a qualified individual on the basis of disability. Discrimination includes not making reasonable accommodations to the known physical or mental limitations of an otherwise qualified individual, see § 12112(b)(5)(A)."),
    ("29 U.S.C. § 623", "USC", 29, "623", "Prohibition of age discrimination", "adea",
     "It shall be unlawful for an employer to fail or refuse to hire or to discharge any individual or otherwise discriminate against any individual because of such individual's age."),
    ("29 C.F.R. § 1630.2", "CFR", 29, "1630.2", "Definitions", "ada",
     "Reasonable accommodation means modifications or adjustments to the work environment, or to the manner or circumstances under which the position is customarily performed, that enable a qualified individual with a disability to perform the essential functions."),
]


@pytest.fixture
def corpus(session):
    session.add_all([CourtRow(id="scotus", name="Supreme Court of the United States", short_name="SCOTUS", level="supreme"),
                     CourtRow(id="ca5", name="Court of Appeals for the Fifth Circuit", short_name="5th Cir.", level="appeals", circuit="5")])
    session.flush()
    ids: dict[str, int] = {}
    for key, name, cite, court, year, texts in OPINIONS:
        op = Opinion(court_id=court, case_name=name, citation=cite, year=year, date_filed=f"{year}-01-01",
                     plain_text=" ".join(texts), source="fixture", source_id=key, url=f"https://x/{key}")
        session.add(op)
        session.flush()
        ids[key] = op.id
        for i, t in enumerate(texts):
            session.add(Chunk(kind="opinion", opinion_id=op.id, ordinal=i, text=t))
    for cite, code, title, sec, heading, statute, t in STATUTES:
        row = StatuteSection(code=code, title=title, section=sec, citation=cite, heading=heading, statute=statute, text=t)
        session.add(row)
        session.flush()
        ids[f"sec{sec}"] = row.id
        session.add(Chunk(kind="regulation" if code == "CFR" else "statute", section_id=row.id, text=t))
    session.commit()
    return ids


@pytest.fixture
def retriever(session, session_factory, settings, corpus):
    HybridRetriever.build_index(session)
    return HybridRetriever(session_factory, settings)


def test_missing_index_error(session_factory, settings, corpus):
    with pytest.raises(IndexNotBuiltError, match="stare index build"):
        HybridRetriever(session_factory, settings).search("anything")


def test_build_stores_embeddings(session, settings, corpus):
    stats = HybridRetriever.build_index(session)
    assert stats["chunks"] == 13
    emb = session.query(Chunk).first().embedding
    assert emb is not None and emb.shape == (settings.embedding_dim,)
    assert all(c.embedding is not None for c in session.query(Chunk))


def test_exact_cite_bm25_top3(retriever, corpus):
    res = retriever.search("411 U.S. 792", k=5)
    assert any(c.opinion_id == corpus["mcd"] and c.bm25_rank in (1, 2, 3) for c in res[:3])
    assert res[0].opinion_id == corpus["mcd"]
    assert all(c.query == "411 U.S. 792" for c in res)


def test_semantic_query_ranks_retaliation(retriever, corpus):
    res = retriever.search("employer punished worker for complaining about discrimination", k=5)
    retaliation = {corpus["burl"], corpus["lowe"], corpus["nassar"], corpus["sec2000e-3"]}
    assert any((c.opinion_id in retaliation or c.section_id == corpus["sec2000e-3"]) for c in res[:3])
    top = res[0]
    assert top.rerank_score is not None and top.rrf_score > 0
    assert [c.rerank_score for c in res] == sorted((c.rerank_score for c in res), reverse=True)


def test_statute_number_query(retriever, corpus):
    res = retriever.search("§ 12112(b)(5)(A) reasonable accommodation", k=3)
    assert res[0].section_id == corpus["sec12112"]


def test_filters(retriever, corpus):
    only_stat = retriever.search("discrimination employer", k=20, kinds={"statute"})
    assert only_stat and all(c.kind == "statute" for c in only_stat)
    ca5 = retriever.search("discrimination employer complained", k=20, court_ids={"ca5"})
    assert ca5 and all(c.opinion_id == corpus["lowe"] for c in ca5)
    assert retriever.search("discrimination", court_ids={"nope"}) == []


def test_search_many_fusion(retriever, corpus):
    qs = ["411 U.S. 792 prima facie case", "reasonable accommodation disability", "age but-for cause"]
    res = retriever.search_many(qs, k=13)
    opinions = {c.opinion_id for c in res}
    assert {corpus["mcd"], corpus["gross"], corpus["barnett"]} <= opinions
    per_query = [retriever.search(q, k=13) for q in qs]
    expected: dict[int, float] = {}
    for lst in per_query:
        for rank, c in enumerate(lst, 1):
            expected[c.chunk_id] = expected.get(c.chunk_id, 0.0) + 1 / (60 + rank)
    for c in res:
        assert c.rrf_score == pytest.approx(expected[c.chunk_id])
    scores = [c.rrf_score for c in res]
    assert scores == sorted(scores, reverse=True)
    assert len({c.chunk_id for c in res}) == len(res)
    assert {c.query for c in res} <= set(qs)


def test_authorities_grouping(retriever, corpus):
    chunks = retriever.search("retaliation reasonable worker dissuaded charge of discrimination", k=10)
    auths = retriever.authorities_from_chunks(chunks, limit=4)
    keys = [a.key for a in auths]
    assert len(keys) == len(set(keys)) <= 4
    first_seen = []
    for c in chunks:
        k = f"op:{c.opinion_id}" if c.opinion_id else f"sec:{c.section_id}"
        if k not in first_seen:
            first_seen.append(k)
    assert keys == first_seen[: len(keys)]  # best-first order preserved
    rel = [a.relevance for a in auths]
    assert rel[0] == 1.0 and rel == sorted(rel, reverse=True) and all(0 <= r <= 1 for r in rel)
    a = next(a for a in auths if a.key == f"op:{corpus['burl']}")
    assert a.kind == "case" and a.citation == "548 U.S. 53" and a.court_id == "scotus"
    assert a.court_name and a.year == 2006 and a.url and a.opinion_id == corpus["burl"]
    assert 1 <= len(a.passages) <= 3
    sec = retriever.authorities_from_chunks(retriever.search("29 C.F.R. § 1630.2 reasonable accommodation", k=5), 5)
    reg = next(x for x in sec if x.key == f"sec:{corpus['sec1630.2']}")
    assert reg.kind == "regulation" and reg.citation == "29 C.F.R. § 1630.2" and reg.section_id


def test_save_load_roundtrip_and_cache(session, session_factory, settings, corpus):
    HybridRetriever.build_index(session)
    r1 = HybridRetriever(session_factory, settings)
    r2 = HybridRetriever(session_factory, settings)  # fresh instance loads from disk
    a = [(c.chunk_id, c.rerank_score) for c in r1.search("but-for causation retaliation", k=5)]
    b = [(c.chunk_id, c.rerank_score) for c in r2.search("but-for causation retaliation", k=5)]
    assert a == b
    assert r1._matrix is not None and r1._loaded_mtime is not None


def test_stale_index(session, session_factory, settings, corpus):
    HybridRetriever.build_index(session)
    session.add(Chunk(kind="opinion", opinion_id=corpus["mcd"], ordinal=9, text="new chunk"))
    session.commit()
    with pytest.raises(IndexStaleError, match="stare index build"):
        HybridRetriever(session_factory, settings).search("anything")
    HybridRetriever.build_index(session)  # rebuild fixes it
    assert HybridRetriever(session_factory, settings).search("new chunk", k=1)


def test_cli_app_has_commands():
    from stare.retrieval.cli import index_app

    names = {c.name or c.callback.__name__ for c in index_app().registered_commands}
    assert names == {"build", "search"}
