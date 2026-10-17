"""Mata v. Avianca acceptance test: none of the invented citations may reach a memo."""

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from test_citations_support import add_opinion, mock_client, seed_corpus

from stare.citations.firewall import CitationFirewall, FirewallReport
from stare.db.models import Opinion

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "data" / "eval" / "mata_citations.json"
ENTRIES = json.loads(FIXTURE.read_text())["citations"]
MATA = [e for e in ENTRIES if e["mata"]]


def test_fixture_has_the_six_plus_zicherman():
    assert len(MATA) == 6 and len(ENTRIES) == 7
    assert MATA[0]["citation"] == "Varghese v. China Southern Airlines Co., Ltd., 925 F.3d 1339 (11th Cir. 2019)"
    assert MATA[1]["citation"] == "Shaboon v. Egyptair, 2013 IL App (1st) 111279-U (Ill. App. Ct. 2013)"
    assert MATA[3]["citation"].startswith("Martinez v. Delta Air Lines, Inc., 2019 WL 4639462")
    assert ENTRIES[-1]["citation"].startswith("Zicherman v. Korean Air Lines Co., Ltd., 516 F.3d 1237")
    assert json.loads((Path(__file__).parent / "fixtures/citations/mata_citations.json").read_text()) == json.loads(FIXTURE.read_text())


def _sentence(e):
    return f"The airline is liable under the Montreal Convention. {e['citation']}."


@pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e["cite"])
def test_not_exportable_with_api_disabled(entry, session, session_factory, settings):
    seed_corpus(session)
    fw = CitationFirewall(session_factory, settings, client=None)
    checks = fw.verify_text(_sentence(entry))
    assert len(checks) == 1
    assert checks[0].status in ("blocked", "unresolved") and not checks[0].exportable
    assert checks[0].reason


@pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e["cite"])
def test_blocked_when_api_says_not_found(entry, session, session_factory, settings):
    seed_corpus(session)
    fw = CitationFirewall(session_factory, settings, client=mock_client(settings, token="test-token"))
    check = fw.verify_text(_sentence(entry))[0]
    assert check.status == "blocked" and not check.exportable
    assert "no matching opinion in index or API" in check.reason


def test_all_six_removed_from_a_memo_paragraph(session, session_factory, settings):
    seed_corpus(session)
    fw = CitationFirewall(session_factory, settings, client=mock_client(settings, token="test-token"))
    text = " ".join(f"Point {i}. See {e['citation']}." for i, e in enumerate(MATA, 1)) + " Retaliation is barred. 42 U.S.C. § 2000e-3(a)."
    checks = fw.verify_text(text)
    assert [c.status for c in checks[:6]] == ["blocked"] * 6 and checks[6].status == "verified"
    clean, removed = fw.filter_text(text, checks)
    assert len(removed) == 6
    for e in MATA:
        assert e["cite"] not in clean
    assert "Retaliation is barred" in clean
    assert FirewallReport(checks).summary() == "7 checked: 1 verified, 6 blocked"


def test_real_reporter_page_with_different_case_name_is_blocked(session, session_factory, settings):
    """Several Mata fakes point at real reporter pages that belong to other cases."""
    add_opinion(session, "Smith v. Acme Logistics, Inc.", "925 F.3d 1339", year=2019)
    session.commit()
    fw = CitationFirewall(session_factory, settings, client=None)
    check = fw.verify_text(MATA[0]["citation"] + ".")[0]
    assert check.status == "blocked" and not check.exportable
    assert "belongs to 'Smith v. Acme Logistics, Inc.'" in check.reason and "Varghese" in check.reason
    g2 = check.gates[1]
    assert g2.outcome == "fail" and g2.score is not None and g2.score < 0.6


def test_same_page_with_matching_name_is_not_blocked(session, session_factory, settings):
    add_opinion(session, "Varghese v. China Southern Airlines Co., Ltd.", "925 F.3d 1339", year=2019)
    session.commit()
    assert CitationFirewall(session_factory, settings).verify_text(MATA[0]["citation"] + ".")[0].status == "verified"


def test_real_zicherman_would_pass_but_fake_does_not(session, session_factory, settings):
    add_opinion(session, "Zicherman v. Korean Air Lines Co.", "516 U.S. 217", year=1996)
    session.commit()
    fw = CitationFirewall(session_factory, settings)
    assert fw.verify_text("Zicherman v. Korean Air Lines Co., 516 U.S. 217 (1996).")[0].status == "verified"
    assert fw.verify_text(ENTRIES[-1]["citation"] + ".")[0].exportable is False


def test_against_real_seed_corpus_if_present(settings):
    """Runs only when the ingest agent has built data/stare.db."""
    db = REPO / "data" / "stare.db"
    if not db.exists():
        pytest.skip("data/stare.db not built")
    engine = create_engine(f"sqlite:///{db}")
    try:
        with sessionmaker(bind=engine)() as s:
            if not s.scalar(select(func.count()).select_from(Opinion)):
                pytest.skip("seed corpus is empty")
    except Exception:
        pytest.skip("seed database has no usable opinions table")
    fw = CitationFirewall(sessionmaker(bind=engine), settings, client=None)
    for e in ENTRIES:
        c = fw.verify_text(_sentence(e))[0]
        assert not c.exportable, (e["citation"], c.status, c.reason)
