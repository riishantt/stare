from __future__ import annotations

import pytest

from stare.courts.hierarchy import AuthorityRanker, CourtHierarchy


@pytest.fixture(scope="module")
def h() -> CourtHierarchy:
    return CourtHierarchy.default()


def test_registry_counts(h):
    courts = h.all()
    assert len([c for c in courts if c.level == "supreme"]) == 1
    assert len([c for c in courts if c.level == "appellate"]) == 13
    assert len([c for c in courts if c.level == "district"]) == 94
    assert len({c.id for c in courts}) == len(courts)


def test_get_and_circuit(h):
    assert h.get("txnd").short_name == "N.D. Tex."
    assert h.get("txnd").circuit == "5"
    assert h.get("cand").circuit == "9"
    assert h.get("dcd").circuit == "dc"
    assert h.circuit_of("scotus") is None
    assert h.circuit_of("nope") is None
    assert h.get("nope") is None


@pytest.mark.parametrize(
    "text,expected",
    [
        ("N.D. Tex.", "txnd"),
        ("N.D. Tex", "txnd"),
        ("ND Tex", "txnd"),
        ("Northern District of Texas", "txnd"),
        ("United States District Court for the Northern District of Texas", "txnd"),
        ("District Court, N.D. Texas", "txnd"),
        ("N.D. Cal.", "cand"),
        ("Northern District of California", "cand"),
        ("S.D.N.Y.", "nysd"),
        ("Southern District of New York", "nysd"),
        ("E.D. Pa.", "paed"),
        ("D.D.C.", "dcd"),
        ("District of Columbia", "dcd"),
        ("D. Mass.", "mad"),
        ("D. Alaska", "akd"),
        ("N.D. W. Va.", "wvnd"),
        ("Northern District of West Virginia", "wvnd"),
        ("W.D. Wash.", "wawd"),
        ("Western District of Washington", "wawd"),
        ("5th Cir.", "ca5"),
        ("Fifth Circuit", "ca5"),
        ("fifth circuit", "ca5"),
        ("(5th Cir. 1997)", "ca5"),
        ("United States Court of Appeals for the Fifth Circuit", "ca5"),
        ("Court of Appeals, Ninth Circuit", "ca9"),
        ("9th Circuit", "ca9"),
        ("2d Cir.", "ca2"),
        ("2nd Circuit", "ca2"),
        ("3d Cir.", "ca3"),
        ("11th Cir.", "ca11"),
        ("D.C. Cir.", "cadc"),
        ("Court of Appeals for the District of Columbia Circuit", "cadc"),
        ("Fed. Cir.", "cafc"),
        ("Federal Circuit", "cafc"),
        ("U.S.", "scotus"),
        ("Supreme Court of the United States", "scotus"),
        ("scotus", "scotus"),
        ("txsd", "txsd"),
    ],
)
def test_normalize(h, text, expected):
    assert h.normalize(text) == expected


@pytest.mark.parametrize("text", ["", "   ", None, "Superior Court of California", "Texas Supreme Court", "Moon"])
def test_normalize_unknown(h, text):
    assert h.normalize(text) is None


def test_every_court_normalizes_from_its_own_names(h):
    for c in h.all():
        assert h.normalize(c.short_name) == c.id, c
        assert h.normalize(c.name) == c.id, c


@pytest.fixture(scope="module")
def ranker() -> AuthorityRanker:
    return AuthorityRanker()


@pytest.mark.parametrize(
    "deciding,published,status,weight",
    [
        ("scotus", True, "binding", 1.0),
        ("ca5", True, "binding", 0.9),
        ("ca5", False, "persuasive", 0.6),
        ("txsd", True, "persuasive", 0.5),
        ("txnd", True, "persuasive", 0.5),
        ("lawd", True, "persuasive", 0.5),
        ("ca9", True, "persuasive", 0.4),
        ("ca9", False, "persuasive", 0.3),
        ("cand", True, "persuasive", 0.3),
        ("nysd", True, "persuasive", 0.3),
        ("zzz", True, "persuasive", 0.2),
        (None, True, "persuasive", 0.2),
    ],
)
def test_table_26_for_ndtex(ranker, deciding, published, status, weight):
    r = ranker.rank(deciding, "txnd", published=published)
    assert (r.status, r.weight) == (status, weight)
    assert r.reason


def test_table_26_for_ndcal(ranker):
    assert ranker.rank("ca9", "cand").weight == 0.9
    assert ranker.rank("ca5", "cand").weight == 0.4
    assert ranker.rank("cacd", "cand").weight == 0.5


def test_negative_treatment_flags(ranker):
    r = ranker.rank("scotus", "txnd", negative_treatment=True)
    assert r.status == "flagged" and r.weight == 0.0
    assert r.reason == "Gate 4 warning: not used until reviewed"


def test_reason_is_human_readable(ranker):
    assert ranker.rank("ca5", "txnd").reason == "Court of appeals for Texas (Fifth Circuit), published"
    assert "Ninth Circuit" in ranker.rank("ca9", "txnd").reason


def test_unknown_filing_court(ranker):
    assert ranker.rank("scotus", None).weight == 1.0
    assert ranker.rank("ca5", None).status == "persuasive"
