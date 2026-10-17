import io

from docx import Document

from stare.export.docx_exporter import MemoExporter
from stare.schemas import CitationCheck, ExtractedCitation, GateResult, Memo, MemoCitation


def _memo() -> Memo:
    return Memo(
        title="Research Memorandum: Title VII Retaliation",
        question_presented="Can the client state a retaliation claim?",
        issue="Whether the termination was retaliatory.",
        rule="A plaintiff must show **but-for** causation. *Univ. of Tex. Sw. Med. Ctr. v. Nassar* [1].",
        application="- Protected activity in May 2026\n- Termination in March 2026",
        conclusion="The claim is viable.",
        adverse_authority="Clark County School Dist. v. Breeden [2] requires very close temporal proximity.",
        warnings=["Toyota Motor Mfg. v. Williams was superseded by the ADA Amendments Act of 2008."],
        citations=[
            MemoCitation(marker="[1]", citation="570 U.S. 338", case_name="Univ. of Tex. Sw. Med. Ctr. v. Nassar",
                         url="https://www.courtlistener.com/?q=570+U.S.+338"),
            MemoCitation(marker="[2]", citation="532 U.S. 268", case_name="Clark County School Dist. v. Breeden"),
        ],
        removed_citations=["Varghese v. China Southern Airlines Co., 925 F.3d 1339 (11th Cir. 2019)"],
    )


def test_docx_roundtrip_contains_sections_and_appendix():
    check = CitationCheck(
        citation=ExtractedCitation(raw="570 U.S. 338", cite="570 U.S. 338"),
        gates=[GateResult(gate=1, name="extract", outcome="pass"), GateResult(gate=2, name="exists", outcome="pass")],
        status="verified",
        reason="quote matched; no negative treatment",
    )
    data = MemoExporter().to_docx(_memo(), {"matter_number": "M-0142", "run_id": 3, "checks": [check.model_dump()]})
    doc = Document(io.BytesIO(data))
    text = "\n".join(p.text for p in doc.paragraphs)
    for heading in ("Issue", "Rule", "Application", "Conclusion", "Adverse Authority", "Authorities Cited"):
        assert heading in text
    assert "Varghese" in text  # removed citations are listed in the appendix
    assert "Not legal advice" in doc.sections[0].footer.paragraphs[0].text
    table_text = " ".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
    assert "VERIFIED" in table_text and "M-0142" in table_text
