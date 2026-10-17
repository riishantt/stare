import pytest
from test_citations_support import NASSAR_QUOTE, NASSAR_TEXT, add_opinion, mock_client, seed_corpus

from stare.citations.gates import gate_exists, gate_extract, gate_good_law, gate_quote_match
from stare.citations.index import CitationIndex, strip_subsection
from stare.citations.parser import extract_citations
from stare.citations.treatment import mention_patterns, scan_context
from stare.db.models import CitationEdge
from stare.schemas import ExtractedCitation


def cite_of(text):
    return extract_citations(text)[0]


# --- index ----------------------------------------------------------------------------------------
def test_index_lookup_normalises_reporter(session):
    seed_corpus(session)
    idx = CitationIndex(session)
    assert [o.case_name for o in idx.lookup("133", "S.Ct.", "2517")][0].startswith("University of Texas")
    assert idx.lookup("570", "U. S.", "338")
    assert idx.lookup("570", "U.S.", "339") == []
    assert idx.lookup("570", "F.3d", "338") == []


def test_index_statute_lookup_strips_subsection(session):
    seed_corpus(session)
    idx = CitationIndex(session)
    c = cite_of("See 42 U.S.C. § 2000e-3(a)(1).")
    assert idx.lookup_statute(c).section == "2000e-3"
    assert idx.lookup_statute(cite_of("29 C.F.R. § 1630.2(o)")).citation == "29 C.F.R. § 1630.2"
    assert idx.lookup_statute(cite_of("42 U.S.C. § 9999")) is None
    assert strip_subsection("2000e-3(a)(1)") == "2000e-3" and strip_subsection("1630.2(o)") == "1630.2"
    assert "Title VII" in idx.opinion_text(1) or idx.opinion_text(1)


# --- Gate 1 ------------------------------------------------------------------------------------------
def test_gate1():
    assert gate_extract(cite_of("Smith v. Jones, 10 F.3d 20 (4th Cir. 1994)")).outcome == "pass"
    assert gate_extract(ExtractedCitation(raw="Id.", cite="", kind="id")).outcome == "fail"
    assert gate_extract(ExtractedCitation(raw="x", cite="x")).outcome == "fail"


# --- Gate 2 ------------------------------------------------------------------------------------------
def test_gate2_local_pass_and_name_variants(session, settings):
    seed_corpus(session)
    idx = CitationIndex(session)
    c = cite_of("Univ. of Tex. Sw. Med. Ctr. v. Nassar, 570 U.S. 338 (2013).")
    g, ref = gate_exists(c, idx, None, settings)
    assert g.outcome == "pass" and g.score >= 0.95 and ref.source == "local" and ref.opinion_id


def test_gate2_name_mismatch_fails_with_reason(session, settings):
    add_opinion(session, "Smith v. Acme Logistics, Inc.", "925 F.3d 1339", year=2019)
    session.commit()
    c = cite_of("Varghese v. China Southern Airlines Co., Ltd., 925 F.3d 1339 (11th Cir. 2019).")
    g, ref = gate_exists(c, CitationIndex(session), None, settings)
    assert g.outcome == "fail" and ref is None
    assert "belongs to 'Smith v. Acme Logistics, Inc.'" in g.detail and "not 'Varghese" in g.detail


def test_gate2_no_case_name_warns(session, settings):
    seed_corpus(session)
    g, ref = gate_exists(cite_of("The test appears at 411 U.S. 792."), CitationIndex(session), None, settings)
    assert g.outcome == "warn" and ref.opinion_id


def test_gate2_year_mismatch_warns(session, settings):
    seed_corpus(session)
    g, _ = gate_exists(cite_of("McDonnell Douglas Corp. v. Green, 411 U.S. 792 (1999)."), CitationIndex(session), None, settings)
    assert g.outcome == "warn" and "1973" in g.detail


def test_gate2_unavailable_api_is_unresolved(session, settings):
    c = cite_of("Foo v. Bar, 1 F.3d 1 (1st Cir. 1990).")
    g, ref = gate_exists(c, CitationIndex(session), mock_client(settings, lambda r: __import__("httpx").Response(500)), settings)
    assert g.outcome == "unresolved" and ref is None
    settings.courtlistener_enabled = False
    from stare.citations.courtlistener import CourtListenerClient
    assert gate_exists(c, CitationIndex(session), CourtListenerClient(settings), settings)[0].outcome == "unresolved"
    assert gate_exists(c, CitationIndex(session), None, settings)[0].outcome == "unresolved"


def test_gate2_api_not_found_fails(session, settings):
    g, _ = gate_exists(cite_of("Foo v. Bar, 1 F.3d 1 (1st Cir. 1990)."), CitationIndex(session), mock_client(settings, token="test-token"), settings)
    assert g.outcome == "fail" and "no matching opinion in index or API" in g.detail


def test_gate2_api_found_matching_and_mismatching(session, settings):
    client = mock_client(settings, found={"1 F.3d 1": "Foo v. Bar Corp."})
    g, ref = gate_exists(cite_of("Foo v. Bar, 1 F.3d 1 (1st Cir. 2019)."), CitationIndex(session), client, settings)
    assert g.outcome == "pass" and ref.source == "courtlistener" and ref.cluster_id == 77 and ref.url
    g, ref = gate_exists(cite_of("Foo v. Bar, 1 F.3d 1 (1st Cir. 2019)."), CitationIndex(session), client, settings)
    assert ref.source == "cache"
    g, ref = gate_exists(cite_of("Qux v. Zed, 1 F.3d 1 (1st Cir. 2019)."), CitationIndex(session), client, settings)
    assert g.outcome == "fail" and ref is None


def test_gate2_statutes(session, settings):
    seed_corpus(session)
    idx = CitationIndex(session)
    g, ref = gate_exists(cite_of("42 U.S.C. § 2000e-3(a)"), idx, None, settings)
    assert g.outcome == "pass" and ref.source == "statute_index"
    g, ref = gate_exists(cite_of("42 U.S.C. § 1981"), idx, None, settings)
    assert g.outcome == "unresolved"


# --- Gate 3 ------------------------------------------------------------------------------------------
def test_gate3_outcomes(settings):
    assert gate_quote_match("", NASSAR_TEXT, settings).outcome == "skip"
    exact = gate_quote_match(NASSAR_QUOTE.lower() + ".", NASSAR_TEXT, settings)
    assert exact.outcome == "pass" and exact.score >= 0.995
    near = gate_quote_match("Title VII retaliation claims must be proved according to traditional principles of a but-for causation standard", NASSAR_TEXT, settings)
    assert near.outcome == "warn" and 0.9 <= near.score < 0.995
    bad = gate_quote_match("Title VII plaintiffs may recover whenever retaliation was a motivating factor in the decision", NASSAR_TEXT, settings)
    assert bad.outcome == "fail" and bad.score < 0.9
    assert gate_quote_match("some quoted text here", "", settings).outcome == "unresolved"


# --- Gate 4 ------------------------------------------------------------------------------------------
def test_gate4_curated_treatment(session):
    ops = seed_corpus(session)
    g = gate_good_law(ops["toyota"].id, session)
    assert g.outcome == "warn" and "superseded by statute" in g.detail and "ADA Amendments Act of 2008" in g.detail
    assert gate_good_law(ops["mcd"].id, session).outcome == "pass"
    assert gate_good_law(None, session).outcome == "skip"


def test_gate4_citing_case_context_scan(session):
    ops = seed_corpus(session)
    later = add_opinion(session, "Later v. Employer", "700 F.3d 100", year=2015, text=(
        "Plaintiff relies on McDonnell Douglas Corp. v. Green, 411 U.S. 792 (1973), which was overruled "
        "by Congress in the statute, as courts have recognised. Other text."))
    session.add(CitationEdge(citing_id=later.id, cited_id=ops["mcd"].id))
    session.commit()
    g = gate_good_law(ops["mcd"].id, session)
    assert g.outcome == "warn" and "overruled" in g.detail and "Later v. Employer" in g.detail


def test_gate4_edge_label_and_clean_edges(session):
    ops = seed_corpus(session)
    neg = add_opinion(session, "Neg v. Case", "701 F.3d 1", text="We discuss it.")
    pos = add_opinion(session, "Pos v. Case", "702 F.3d 1", text="We follow McDonnell Douglas Corp. v. Green, 411 U.S. 792, faithfully.")
    session.add_all([CitationEdge(citing_id=neg.id, cited_id=ops["nassar"].id, treatment="negative:abrogated"),
                     CitationEdge(citing_id=pos.id, cited_id=ops["mcd"].id, treatment="positive")])
    session.commit()
    g = gate_good_law(ops["nassar"].id, session)
    assert g.outcome == "warn" and "abrogated by Neg v. Case" in g.detail
    assert gate_good_law(ops["mcd"].id, session).outcome == "pass"


# --- treatment scanner: false positives ---------------------------------------------------------------
PATS = mention_patterns("Foo Corp. v. Bar", ["100 U.S. 200"])


@pytest.mark.parametrize("text", [
    "The court of appeals reversed the district court in an unrelated matter involving Baz. See Foo Corp. v. Bar, 100 U.S. 200 (1990).",
    "We have not overruled Foo Corp. v. Bar, 100 U.S. 200, and we decline to do so.",
    "Qux, 5 U.S. 1, was overruled by Foo Corp. v. Bar, 100 U.S. 200 (1990).",  # Foo is the overruler
    "Foo Corp. v. Bar, 100 U.S. 200 (1990). Defendant's objection to the exhibit is overruled.",
    "Foo Corp. v. Bar, 100 U.S. 200, applies. " + "x" * 400 + " The prior decision was overruled.",  # far away
    "Foo, 100 U.S. 200; Other v. Case, 7 U.S. 3 (1801), overruled in part on other grounds.",  # about another cite
    "In Foo Corp. v. Bar, 100 U.S. 200, 205 (1990), the Court reversed the Sixth Circuit.",  # Foo did the reversing
    "Foo Corp. v. Bar, 100 U.S. 200 (1990), abrogated Qux v. Quux, 5 F.3d 1 (1st Cir. 1985).",  # active voice
])
def test_scanner_avoids_false_positives(text):
    assert scan_context(text, PATS) == []


@pytest.mark.parametrize("text,label", [
    ("Foo Corp. v. Bar, 100 U.S. 200 (1990), was overruled by Next v. Case.", "overruled"),
    ("Later cases hold that Foo Corp. v. Bar has been abrogated by statute.", "abrogated"),
    ("The holding of 100 U.S. 200 was superseded by statute, the ADA Amendments Act of 2008.", "superseded by statute"),
    ("Foo Corp. v. Bar, 100 U.S. 200 (1990), rev'd, 200 U.S. 1 (1991).", "reversed"),
    ("Foo Corp. v. Bar is no longer good law after the amendment.", "no longer good law"),
    ("Foo Corp. v. Bar, 100 U.S. 200, 205 (5th Cir. 1990), vacated, 3 U.S. 4 (1991).", "reversed"),
    ("Foo, 100 U.S. 200, was later vacated by the en banc court.", "reversed"),
])
def test_scanner_detects_treatment(text, label):
    assert [f.label for f in scan_context(text, PATS)][:1] == [label]


def test_gate4_cited_by_snippets_from_api(session, settings):
    import httpx
    ops = seed_corpus(session)
    def h(req):
        return httpx.Response(200, json={"results": [{"cluster_id": 2, "caseName": "Later v. X", "opinions": [{"snippet": "this rule is no longer good law"}]}]})
    g = gate_good_law(ops["mcd"].id, session, mock_client(settings, h), cluster_id=5)
    assert g.outcome == "warn" and "Later v. X" in g.detail


def test_gate2_anonymous_search_miss_is_unresolved_not_nonexistent(session, settings):
    """The public search index can miss real opinions, so only the authenticated lookup proves non-existence."""
    g, _ = gate_exists(cite_of("Burwell v. Hobby Lobby Stores, Inc., 573 U.S. 682 (2014)."), CitationIndex(session),
                       mock_client(settings), settings)
    assert g.outcome == "unresolved" and "could not be confirmed" in g.detail
