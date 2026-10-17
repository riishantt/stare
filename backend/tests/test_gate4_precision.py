"""Gate 4 precision: who overruled whom, and which courts can overrule which precedents."""

from stare.citations.gates import gate_good_law
from stare.citations.treatment import has_authority_over
from stare.courts.hierarchy import CourtHierarchy
from stare.db.models import Citation, CitationEdge, CourtRow, Opinion


def _court(session, cid, level, circuit=None):
    session.merge(CourtRow(id=cid, name=cid, short_name=cid, level=level, circuit=circuit))


def _op(session, name, cite, court, text="Opinion text."):
    vol, rep, page = cite.split(" ", 1)[0], cite.rsplit(" ", 1)[0].split(" ", 1)[1], cite.rsplit(" ", 1)[1]
    op = Opinion(case_name=name, citation=cite, court_id=court, plain_text=text, source="fixture", source_id=cite)
    session.add(op)
    session.flush()
    session.add(Citation(opinion_id=op.id, volume=vol, reporter=rep, page=page, cite=cite))
    return op


def _setup(session):
    _court(session, "scotus", "supreme")
    _court(session, "ca5", "appellate", "5")
    _court(session, "ca9", "appellate", "9")
    session.flush()


def test_authority_rules():
    h = CourtHierarchy.default()
    assert has_authority_over("scotus", "ca5", h)
    assert not has_authority_over("ca5", "scotus", h)
    assert has_authority_over("ca5", "ca5", h) and has_authority_over("ca5", "txnd", h)
    assert not has_authority_over("ca9", "ca5", h)
    assert not has_authority_over("txnd", "ca5", h)


def test_this_case_as_the_overruler_is_not_negative(session):
    _setup(session)
    bn = _op(session, "Burlington Northern & Santa Fe Railway Co. v. White", "548 U.S. 53", "scotus")
    later = _op(session, "EEOC v. Boh Bros. Construction Co.", "731 F.3d 444", "ca5", text=(
        "See Mattern v. Eastman Kodak Co., 104 F.3d 702 (5th Cir. 1997), abrogated on other grounds by "
        "Burlington Northern & Santa Fe Railway Co. v. White, 548 U.S. 53 (2006)."))
    session.add(CitationEdge(citing_id=later.id, cited_id=bn.id))
    session.commit()
    assert gate_good_law(bn.id, session).outcome == "pass"


def test_lower_court_cannot_overrule_supreme_court(session):
    _setup(session)
    reeves = _op(session, "Reeves v. Sanderson Plumbing Products, Inc.", "530 U.S. 133", "scotus")
    later = _op(session, "Russell v. McKinney Hospital Venture", "235 F.3d 219", "ca5", text=(
        "Reeves v. Sanderson Plumbing Products, Inc., 530 U.S. 133 (2000), overruled our prior pretext-plus rule."))
    session.add(CitationEdge(citing_id=later.id, cited_id=reeves.id))
    session.commit()
    assert gate_good_law(reeves.id, session).outcome == "pass"


def test_same_circuit_en_banc_overruling_is_flagged(session):
    _setup(session)
    old = _op(session, "Mattern v. Eastman Kodak Co.", "104 F.3d 702", "ca5")
    en_banc = _op(session, "Hamilton v. Dallas County", "79 F.4th 494", "ca5", text=(
        "We therefore overrule Mattern v. Eastman Kodak Co. to the extent it limited actionable conduct "
        "to ultimate employment decisions."))
    session.add(CitationEdge(citing_id=en_banc.id, cited_id=old.id))
    session.commit()
    g = gate_good_law(old.id, session)
    assert g.outcome == "warn" and "Hamilton" in g.detail


def test_gate3_warns_when_quote_is_only_in_a_dissent():
    from stare.citations.gates import gate_quote_match
    from stare.text import part_marker

    text = "The opinion of the court holds that retaliation requires but-for causation.\n\n" + \
        part_marker("dissent", "Justice Ginsburg") + "\nThe motivating-factor standard should govern retaliation claims."
    assert gate_quote_match("retaliation requires but-for causation", text).outcome == "pass"
    g = gate_quote_match("The motivating-factor standard should govern retaliation claims.", text)
    assert g.outcome == "warn" and "dissenting" in g.detail
