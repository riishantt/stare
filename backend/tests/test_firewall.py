import pytest
from test_citations_support import MCD_QUOTE, NASSAR_QUOTE, mock_client, seed_corpus

from stare.citations.firewall import CitationFirewall, FirewallReport
from stare.schemas import Authority

NEAR = MCD_QUOTE.replace("racial discrimination", "gender discrimination")
MISQUOTE = "an employer is strictly liable for every adverse action regardless of motive"

PARAGRAPH = (
    f'Retaliation requires but-for cause. "{NASSAR_QUOTE}." Univ. of Tex. Sw. Med. Ctr. v. Nassar, 570 U.S. 338, 360 (2013). '
    "Id. at 362.\n\n"
    f'The initial burden is on the plaintiff. McDonnell Douglas Corp. v. Green, 411 U.S. 792, 802 (1973) ("{NEAR}"). '
    f'Plaintiffs always win in Univ. of Tex. Sw. Med. Ctr. v. Nassar, 570 U.S. 338 (2013) ("{MISQUOTE}"). '
    "Disability is read narrowly. Toyota Motor Mfg., Ky., Inc. v. Williams, 534 U.S. 184 (2002). "
    "Retaliation is barred. 42 U.S.C. § 2000e-3(a)."
)


@pytest.fixture
def fw(session, session_factory, settings):
    seed_corpus(session)
    return CitationFirewall(session_factory, settings, client=None)


def by_cite(checks):
    return {(c.citation.kind, c.citation.cite, c.citation.quote[:12]): c for c in checks}


def test_verify_text_mixed_paragraph(fw):
    checks = fw.verify_text(PARAGRAPH)
    assert [c.status for c in checks] == ["verified", "verified", "warning", "blocked", "warning", "verified"]
    nassar, idc, mcd, bad, toyota, statute = checks
    assert nassar.gates[2].outcome == "pass" and nassar.opinion_id and nassar.source == "local"
    assert idc.citation.kind == "id" and idc.matched_case_name.startswith("University")
    assert mcd.gates[2].outcome == "warn" and 0.9 <= mcd.gates[2].score < 0.995
    assert bad.status == "blocked" and "quotation not found" in bad.reason and not bad.exportable
    assert toyota.treatment == ["superseded by statute: ADA Amendments Act of 2008, Pub. L. 110-325 (Congress rejected the demanding standard)"]
    assert "superseded by statute" in toyota.reason and toyota.exportable  # shown to the attorney, never removed
    assert statute.source == "statute_index" and statute.gates[3].outcome == "skip"
    for c in checks:
        assert [g.gate for g in c.gates] == [1, 2, 3, 4]


def test_filter_text_removes_only_failing_sentences(fw):
    checks = fw.verify_text(PARAGRAPH)
    clean, removed = fw.filter_text(PARAGRAPH, checks)
    assert len(removed) == 1 and removed[0].startswith("Univ. of Tex.")
    assert "Plaintiffs always win" not in clean and MISQUOTE not in clean
    for kept in ("Retaliation requires but-for cause", "Id. at 362", "The initial burden", "Disability is read narrowly", "42 U.S.C. § 2000e-3(a)"):
        assert kept in clean
    assert "\n\nThe initial burden" in clean and "  " not in clean


def test_filter_text_removes_unresolved_and_whole_paragraph_cleanly(fw):
    text = "Intro sentence stays. Foo v. Bar, 1 F.3d 1 (1st Cir. 2019).\n\nSecond paragraph stays."
    checks = fw.verify_text(text)
    assert checks[0].status == "unresolved"  # API disabled and nothing local
    clean, removed = fw.filter_text(text, checks)
    assert clean == "Intro sentence stays.\n\nSecond paragraph stays."
    assert removed == ["Foo v. Bar, 1 F.3d 1 (1st Cir. 2019)"]


def test_filter_text_noop_when_all_pass(fw):
    t = "Retaliation is barred. 42 U.S.C. § 2000e-3(a)."
    assert fw.filter_text(t, fw.verify_text(t)) == (t, [])


def test_filter_text_does_not_split_on_abbreviations(fw):
    t = 'Plaintiffs always win under Univ. of Tex. Sw. Med. Ctr. v. Nassar, 570 U.S. 338 (2013) ("' + MISQUOTE + '"). Next sentence stays.'
    clean, removed = fw.filter_text(t, fw.verify_text(t))
    assert clean == "Next sentence stays." and len(removed) == 1


def test_unresolved_never_exportable_and_api_not_found_blocks(session, session_factory, settings):
    seed_corpus(session)
    text = "Foo v. Bar, 1 F.3d 1 (1st Cir. 2019)."
    off = CitationFirewall(session_factory, settings, client=None).verify_text(text)[0]
    assert off.status == "unresolved" and not off.exportable
    on = CitationFirewall(session_factory, settings, client=mock_client(settings, token="test-token")).verify_text(text)[0]
    assert on.status == "blocked" and "no matching opinion in index or API" in on.reason and not on.exportable


def test_api_found_without_local_text_quote_unresolved(session, session_factory, settings):
    client = mock_client(settings, found={"1 F.3d 1": "Foo v. Bar"})
    fw = CitationFirewall(session_factory, settings, client=client)
    ok = fw.verify_text("Foo v. Bar, 1 F.3d 1 (1st Cir. 2019).")[0]
    assert ok.status == "verified" and ok.source == "courtlistener"
    q = fw.verify_text('Foo v. Bar, 1 F.3d 1 (1st Cir. 2019) ("some quoted passage of the opinion").')[0]
    assert q.status == "unresolved" and "opinion text unavailable" in q.reason


def test_id_without_antecedent_is_unresolved(fw):
    c = fw.verify_text("Id. at 5.")[0]
    assert c.status == "unresolved" and not c.exportable


def test_verify_authority(fw):
    good = fw.verify_authority(Authority(key="op:1", kind="case", citation="570 U.S. 338",
                                         case_name="University of Texas Southwestern Medical Center v. Nassar", year=2013, quote=NASSAR_QUOTE))
    assert good.status == "verified" and good.opinion_id
    bad = fw.verify_authority(Authority(key="op:1", kind="case", citation="570 U.S. 338", case_name="Wrong v. Name"))
    assert bad.status == "blocked"
    misq = fw.verify_authority(Authority(key="op:1", kind="case", citation="570 U.S. 338",
                                         case_name="Nassar", quote=MISQUOTE))
    assert misq.status == "blocked"
    law = fw.verify_authority(Authority(key="sec:1", kind="statute", citation="42 U.S.C. § 2000e-3(a)"))
    assert law.status == "verified"
    junk = fw.verify_authority(Authority(key="x", kind="case", citation="not a citation"))
    assert junk.status == "unresolved"


def test_report_summary(fw):
    checks = fw.verify_text(PARAGRAPH)
    r = FirewallReport.from_checks(checks)
    assert r.counts == {"verified": 3, "warning": 2, "blocked": 1, "unresolved": 0}
    assert r.summary() == "6 checked: 3 verified, 2 warning, 1 blocked"
    assert not r.exportable and len(r.removed()) == 1 and len(r.warnings()) == 2
    assert FirewallReport([]).summary() == "0 checked: 0 verified"


def test_quotation_in_the_sentence_after_its_citation_is_checked(fw):
    from stare.agents.memo_firewall import check_memo, export_violations
    from stare.schemas import Memo

    text = ("In Univ. of Tex. Sw. Med. Ctr. v. Nassar, 570 U.S. 338 (2013) [1], the Court addressed causation. "
            f'It held that "{MISQUOTE}." Other prose stays.')
    c = fw.verify_text(text)[0]
    assert c.citation.quote.startswith("an employer is strictly liable") and c.status == "blocked"
    clean, removed = fw.filter_text(text, [c])
    assert clean == "Other prose stays." and removed  # the quotation does not stay behind unchecked
    memo = Memo(title="t", question_presented="q", issue="i", rule=text, application="a", conclusion="c")
    assert export_violations(memo, fw)
    cleaned, _ = check_memo(memo, fw)
    assert MISQUOTE not in cleaned.rule and not export_violations(cleaned, fw)
    good = fw.verify_text(text.replace(MISQUOTE, NASSAR_QUOTE))[0]
    assert good.status == "verified" and next(g for g in good.gates if g.gate == 3).outcome == "pass"


def test_quotation_from_the_complaint_after_a_citation_is_not_attached(fw):
    text = ("Univ. of Tex. Sw. Med. Ctr. v. Nassar, 570 U.S. 338 (2013), requires but-for causation. "
            'The complaint alleges that "the manager fired her two days after the charge."')
    c = fw.verify_text(text)[0]
    assert c.citation.quote == "" and c.status == "verified"
