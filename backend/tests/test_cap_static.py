import json

import httpx

from stare.citations.cap_static import CAPStaticClient
from stare.citations.firewall import CitationFirewall

META = [{"name_abbreviation": "J.D. v. Azar", "decision_date": "2019-06-14", "first_page": "1291", "file_name": "1291-01"},
        {"name_abbreviation": "Cleveland v. Policy Management Systems Corp.", "decision_date": "1999-05-24",
         "first_page": "795", "file_name": "0795-01"}]
CASE = {"casebody": {"opinions": [{"type": "majority", "text": "We hold that pursuit of SSDI benefits does not "
                                   "automatically estop the recipient from pursuing an ADA claim."}]}}


def _transport(calls):
    def handler(request):
        calls.append(str(request.url))
        if request.url.path.endswith("CasesMetadata.json"):
            return httpx.Response(200, json=META)
        if request.url.path.endswith("0795-01.json"):
            return httpx.Response(200, json=CASE)
        return httpx.Response(404)
    return httpx.MockTransport(handler)


def test_lookup_listing_and_cache(settings, monkeypatch):
    monkeypatch.setattr(settings, "cap_lookup_enabled", True)
    calls = []
    cap = CAPStaticClient(settings, transport=_transport(calls))
    assert cap.lookup("526", "U.S.", "795")[0]["case_name"].startswith("Cleveland")
    assert cap.lookup("925", "F.3d", "1339") == []  # volume known, no case begins there
    assert cap.lookup("2019", "WL", "4639462") is None  # not covered
    n = len(calls)
    cap.lookup("526", "U.S.", "795")
    assert len(calls) == n  # served from the disk cache


def test_unreachable_cap_backs_off_after_two_failures(settings, monkeypatch):
    monkeypatch.setattr(settings, "cap_lookup_enabled", True)
    calls, now = [], [0.0]

    def down(request):
        calls.append(str(request.url))
        raise httpx.ConnectTimeout("timed out", request=request)

    cap = CAPStaticClient(settings, transport=httpx.MockTransport(down), clock=lambda: now[0])
    for vol in ("501", "502", "503", "504"):
        assert cap.lookup(vol, "U.S.", "1") is None
    assert len(calls) == 2  # the third and fourth lookups do not wait on the network
    now[0] += 301
    cap.lookup("505", "U.S.", "1")
    assert len(calls) == 3  # tried again after the back-off


def test_firewall_verifies_and_blocks_through_cap(session_factory, settings, monkeypatch):
    monkeypatch.setattr(settings, "cap_lookup_enabled", True)
    fw = CitationFirewall(session_factory, settings)
    fw.cap = CAPStaticClient(settings, transport=_transport([]))
    text = ('Cleveland v. Policy Management Systems Corp., 526 U.S. 795 (1999), held that "pursuit of SSDI benefits does '
            'not automatically estop the recipient from pursuing an ADA claim." '
            "See Varghese v. China Southern Airlines Co., 925 F.3d 1339 (11th Cir. 2019).")
    checks = {c.citation.cite: c for c in fw.verify_text(text)}
    good, fake = checks["526 U.S. 795"], checks["925 F.3d 1339"]
    assert good.status == "verified" and good.source == "cap"
    assert next(g for g in good.gates if g.gate == 3).outcome == "pass"
    assert fake.status == "blocked" and "no case begins" in fake.reason


def test_cap_check_survives_persistence_and_export(session_factory, settings, monkeypatch):
    """A check whose source is CAP is stored as JSON and re-validated by the exporter and the memo revision."""
    from stare.agents.state import dump, load_authorities, load_checks
    from stare.api.auth import create_user
    from stare.db.models import CaseFile, CitationCheckRow, ResearchRun
    from stare.export.docx_exporter import MemoExporter
    from stare.schemas import Authority, Memo

    monkeypatch.setattr(settings, "cap_lookup_enabled", True)
    fw = CitationFirewall(session_factory, settings)
    fw.cap = CAPStaticClient(settings, transport=_transport([]))
    check = fw.verify_text("Cleveland v. Policy Management Systems Corp., 526 U.S. 795 (1999).")[0]
    assert check.source == "cap"
    with session_factory() as s:
        u = create_user(s, "A", "a@firm.test", "correct-horse-battery", "attorney")
        case = CaseFile(matter_number="M-1", title="t", user_id=u.id)
        s.add(case)
        s.flush()
        run = ResearchRun(case_id=case.id, created_by=u.id, thread_id="t1")
        s.add(run)
        s.flush()
        s.add(CitationCheckRow(run_id=run.id, raw_citation=check.citation.raw, status=check.status, check_json=dump(check)))
        s.commit()
        stored = [r.check_json for r in s.query(CitationCheckRow).all()]
    assert load_checks(stored)[0].source == "cap"
    a = Authority(key="cap:1", kind="case", citation="526 U.S. 795", verification=check)
    assert load_authorities([dump(a)])[0].verification.source == "cap"
    memo = Memo(title="t", question_presented="q", issue="i", rule="r", application="a", conclusion="c")
    assert MemoExporter().to_docx(memo, {"checks": stored})
