"""Shared helpers for the citation tests: a tiny corpus and a mocked CourtListener."""

from __future__ import annotations

import httpx

from stare.citations.courtlistener import CourtListenerClient
from stare.db.models import Citation, Opinion, StatuteSection, Treatment

NASSAR_QUOTE = "Title VII retaliation claims must be proved according to traditional principles of but-for causation"
MCD_QUOTE = "The complainant in a Title VII trial must carry the initial burden under the statute of establishing a prima facie case of racial discrimination"
NASSAR_TEXT = (
    "Title VII of the Civil Rights Act of 1964 prohibits discrimination and retaliation. "
    "We hold that " + NASSAR_QUOTE + ", not the lessened causation test stated in " + "§ 2000e-2(m). "
    "This requires proof that the unlawful retaliation would not have occurred in the absence of the alleged wrongful action."
)
MCD_TEXT = (
    "The language of Title VII makes plain the purpose of Congress. " + MCD_QUOTE + ". "
    "The burden then must shift to the employer to articulate some legitimate, nondiscriminatory reason."
)
TOYOTA_TEXT = (
    "To be substantially limited in performing manual tasks, an individual must have an impairment that prevents or "
    "severely restricts the individual from doing activities that are of central importance to most people's daily lives."
)


def add_opinion(session, name, cite, text="", year=2000, court="scotus", source_id=None, extra_cites=()):
    vol, rep, page = _split(cite)
    op = Opinion(case_name=name, citation=cite, year=year, court_id=None, plain_text=text or f"{name}. Opinion text.",
                 source="fixture", source_id=source_id or cite)
    session.add(op)
    session.flush()
    session.add(Citation(opinion_id=op.id, volume=vol, reporter=rep, page=page, cite=cite))
    for c in extra_cites:
        v, r, p = _split(c)
        session.add(Citation(opinion_id=op.id, volume=v, reporter=r, page=p, cite=c, cite_type="parallel"))
    session.flush()
    return op


def _split(cite):
    v, rest = cite.split(" ", 1)
    rep, page = rest.rsplit(" ", 1)
    return v, rep, page


def seed_corpus(session):
    nassar = add_opinion(session, "University of Texas Southwestern Medical Center v. Nassar", "570 U.S. 338", NASSAR_TEXT, 2013,
                         extra_cites=["133 S. Ct. 2517"])
    mcd = add_opinion(session, "McDonnell Douglas Corp. v. Green", "411 U.S. 792", MCD_TEXT, 1973)
    toyota = add_opinion(session, "Toyota Motor Manufacturing, Kentucky, Inc. v. Williams", "534 U.S. 184", TOYOTA_TEXT, 2002)
    session.add(Treatment(opinion_id=toyota.id, kind="superseded_by_statute", by="ADA Amendments Act of 2008, Pub. L. 110-325",
                          note="Congress rejected the demanding standard", severity="warning"))
    session.add(StatuteSection(code="USC", title=42, section="2000e-3", citation="42 U.S.C. § 2000e-3", heading="Other unlawful employment practices",
                               statute="title_vii", text="It shall be an unlawful employment practice for an employer to discriminate against any of his employees because he has opposed any practice made an unlawful employment practice by this subchapter."))
    session.add(StatuteSection(code="CFR", title=29, section="1630.2", citation="29 C.F.R. § 1630.2", heading="Definitions", statute="ada",
                               text="Major life activities include caring for oneself, performing manual tasks, seeing, hearing."))
    session.commit()
    return {"nassar": nassar, "mcd": mcd, "toyota": toyota}


def mock_client(settings, handler=None, *, token="", found: dict | None = None):
    """CourtListenerClient on httpx.MockTransport. `found` maps '925 F.3d 1339' -> case name; others are not found."""
    settings.courtlistener_enabled = True
    settings.courtlistener_token = token
    calls: list[httpx.Request] = []

    def default(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        q = request.url.params.get("q", "")
        if request.url.path.endswith("/citation-lookup/"):
            text = request.content.decode()
            hits = [(c, n) for c, n in (found or {}).items() if c.replace(" ", "+") in text or c in text]
            return httpx.Response(200, json=[
                {"citation": text, "status": 200, "clusters": [{"id": 77, "case_name": n, "citations": [{"volume": c.split()[0], "reporter": c.split()[1], "page": c.split()[2]}],
                                                                "absolute_url": "/opinion/77/x/"}]} for c, n in hits
            ] or [{"citation": text, "status": 404, "clusters": []}])
        if request.url.path.endswith("/search/"):
            hits = [(c, n) for c, n in (found or {}).items() if f'"{c}"' in q]
            return httpx.Response(200, json={"count": len(hits), "results": [
                {"cluster_id": 77, "caseName": n, "citation": [c], "dateFiled": "2019-01-01", "absolute_url": "/opinion/77/x/"} for c, n in hits]})
        return httpx.Response(404, json={})

    client = CourtListenerClient(settings, transport=httpx.MockTransport(handler or default), sleep=lambda s: None)
    client.calls = calls  # type: ignore[attr-defined]
    return client
