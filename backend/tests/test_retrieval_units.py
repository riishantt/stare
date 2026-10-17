"""Unit tests for tokenizer, BM25, RRF, embedder and reranker (no database)."""

from __future__ import annotations

import numpy as np

from stare.config import Settings
from stare.retrieval.bm25 import BM25Index
from stare.retrieval.embed import LSAEmbedder, get_embedder
from stare.retrieval.rerank import LexicalReranker, NoReranker, get_reranker
from stare.retrieval.rrf import rrf
from stare.retrieval.tokenize import reference_tokens, tokenize
from stare.schemas import RetrievedChunk


def test_tokenize_statute_numbers():
    t = tokenize("42 U.S.C. § 2000e-3(a) and 29 C.F.R. § 1630.2(o)(1)")
    assert "2000e-3" in t and "1630.2" in t
    assert "sec:2000e-3" in t and "sec:2000e-3(a)" in t
    assert "sec:1630.2" in t and "sec:1630.2(o)" in t and "sec:1630.2(o)(1)" in t


def test_tokenize_subsection_prefixes():
    t = tokenize("§ 12112(b)(5)(A)")
    assert t[:4] == ["sec:12112", "sec:12112(b)", "sec:12112(b)(5)", "sec:12112(b)(5)(a)"]


def test_reporter_cite_tokens_match_across_spacing():
    assert reference_tokens("411 U.S. 792") == ["cite:411:us:792"]
    assert reference_tokens("see 411 u.s. 792, 802") == ["cite:411:us:792"]
    assert "cite:570:fsupp2d:12" in reference_tokens("570 F. Supp. 2d 12")
    assert "cite:123:f3d:456" in tokenize("Smith, 123 F.3d 456 (5th Cir. 1999)")


def test_stopwords_and_stemming():
    t = tokenize("The employers were retaliating against workers")
    assert "the" not in t and "were" not in t
    assert tokenize("employers") == tokenize("employer")
    assert tokenize("retaliating") == tokenize("retaliate") or "retaliat" in tokenize("retaliating")[0]
    assert tokenize("but-for causation")[0] == "but-for"


def test_bm25_ranking_and_roundtrip(tmp_path):
    ids = [10, 20, 30]
    texts = ["the cat sat on the mat", "dogs chase cats and cats chase mice", "411 U.S. 792 burden shifting"]
    idx = BM25Index()
    idx.build(ids, texts)
    assert idx.search("cats", 3)[0][0] == 20
    assert idx.search("411 U.S. 792", 3)[0][0] == 30
    assert idx.search("zzzz", 3) == []
    assert [i for i, _ in idx.search("cat mat cats", 3, allowed_ids={10, 30})] == [10]
    idx.save(tmp_path / "ix")
    again = BM25Index.load(tmp_path / "ix")
    assert again.search("cats", 3) == idx.search("cats", 3)
    assert again.k1 == 1.5 and again.b == 0.75


def test_bm25_idf_and_length_normalisation():
    idx = BM25Index()
    idx.build([1, 2], ["alpha beta", "alpha " + "filler " * 40])
    s = dict(idx.search("alpha", 2))
    assert s[1] > s[2]  # shorter doc scores higher for the same tf


def test_rrf_math():
    out = dict(rrf([[1, 2, 3], [3, 1]], k=60))
    assert abs(out[1] - (1 / 61 + 1 / 62)) < 1e-12
    assert abs(out[2] - 1 / 62) < 1e-12
    assert abs(out[3] - (1 / 63 + 1 / 61)) < 1e-12
    assert [i for i, _ in rrf([[1, 2, 3], [3, 1]])] == [1, 3, 2]
    assert rrf([]) == []


def test_lsa_embedder_shape_norm_and_roundtrip(tmp_path):
    texts = [f"document number {i} about retaliation and discrimination law" for i in range(6)] + [
        "reasonable accommodation for disability", "age but-for causation standard"
    ]
    e = LSAEmbedder(dim=64)
    e.fit(texts)
    v = e.embed(texts)
    assert v.shape == (8, 64) and v.dtype == np.float32
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-5)
    e.save(tmp_path / "e.joblib")
    v2 = LSAEmbedder.load(tmp_path / "e.joblib").embed(texts)
    assert np.allclose(v, v2, atol=1e-5)
    assert not e.embed(["qqqqq"]).any()  # out-of-vocabulary query -> zero vector


def test_factories_default_lightweight():
    s = Settings()
    assert isinstance(get_embedder(s), LSAEmbedder)
    assert isinstance(get_reranker(s), LexicalReranker)
    assert isinstance(get_reranker(Settings(reranker="none")), NoReranker)


def _chunk(i: int, text: str, rrf_score: float = 0.0, kind="opinion") -> RetrievedChunk:
    return RetrievedChunk(chunk_id=i, kind=kind, opinion_id=i, text=text, rrf_score=rrf_score)


def test_lexical_reranker_prefers_cite_and_overlap():
    chunks = [
        _chunk(1, "A discussion of unrelated procedural matters in the district court."),
        _chunk(2, "Under McDonnell Douglas, 411 U.S. 792, the plaintiff must show a prima facie case."),
        _chunk(3, "Burden shifting frameworks are used in many areas."),
    ]
    out = LexicalReranker().rerank("411 U.S. 792 prima facie case", chunks)
    assert out[0].chunk_id == 2
    assert all(c.rerank_score is not None for c in out)
    assert LexicalReranker().rerank("x", []) == []
