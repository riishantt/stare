"""Case-record extraction (stare.intake.extractor): sub-extractors, sample documents, LLM path."""

from __future__ import annotations

from pathlib import Path

import pytest

from stare.courts.hierarchy import CourtHierarchy
from stare.intake import elements
from stare.intake.extractor import (
    extract_case_record,
    extract_claims,
    extract_court,
    extract_facts,
    extract_key_dates,
    extract_parties,
    extract_posture,
    normalize_date,
)
from stare.intake.pdf_reader import extract_document
from stare.intake.redactor import PIIRedactor
from stare.llm import ChatModel, LLMError, OfflineModel, assert_redacted
from stare.intake.extractor import LLMCaseExtraction

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"
H = CourtHierarchy.default()


@pytest.fixture(scope="module")
def redactor():
    return PIIRedactor("auto")


@pytest.fixture(scope="module")
def ndtex(redactor):
    doc = extract_document((SAMPLES / "complaint_ndtex_title7_retaliation.pdf").read_bytes(), "a.pdf")
    return redactor.redact(doc.text)


# -- sub-extractors -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "caption,cid,circuit",
    [
        ("UNITED STATES DISTRICT COURT\nFOR THE NORTHERN DISTRICT OF TEXAS\nDALLAS DIVISION\n\nX, Plaintiff,", "txnd", "5"),
        ("IN THE UNITED STATES DISTRICT COURT\nNORTHERN DISTRICT OF CALIFORNIA\nSAN FRANCISCO DIVISION\n", "cand", "9"),
        ("United States District Court, S.D.N.Y.\n\nCOMPLAINT", "nysd", "2"),
        ("Filed in N.D. Ill. on the date below.", "ilnd", "7"),
    ],
)
def test_extract_court(caption, cid, circuit):
    got_id, name, got_circuit = extract_court(caption, H)
    assert (got_id, got_circuit) == (cid, circuit)
    assert name and "District Court" in name


def test_extract_court_unknown():
    assert extract_court("A letter with no caption at all.", H) == (None, None, None)


def test_extract_parties_caption_variants():
    t1 = "UNITED STATES DISTRICT COURT\nNORTHERN DISTRICT OF TEXAS\n\n[PLAINTIFF],\nPlaintiff,\n\nv.\n\nACME LOGISTICS, INC.,\nDefendant.\n\nCivil Action No. 1"
    p = extract_parties(t1)
    assert [(x.role, x.name) for x in p] == [("plaintiff", "[PLAINTIFF]"), ("defendant", "Acme Logistics, Inc.")]
    # OCR sometimes drops the "v." line
    t2 = "UNITED STATES DISTRICT COURT\n\n[PLAINTIFF],\nPlaintiff,\n\nBRIGHTHARBOR SOFTWARE, INC.,\nDefendant.\n\nCase No. 3:26-cv-1"
    assert [x.name for x in extract_parties(t2)] == ["[PLAINTIFF]", "Brightharbor Software, Inc."]
    # one-line caption
    t3 = "[PERSON_1], Plaintiff, v. Globex Corporation, Defendant."
    assert [x.name for x in extract_parties(t3)] == ["[PERSON_1]", "Globex Corporation"]


def test_extract_claims_from_count_headings():
    t = (
        "FACTS\n1. x.\nCOUNT I — Retaliation in Violation of Title VII, 42 U.S.C. § 2000e-3\n2. y.\n"
        "COUNT II: Failure to Accommodate in Violation of the Americans with Disabilities Act\n3. z.\n"
        "COUNT III - Hostile Work Environment (Title VII)\nCOUNT IV - Age Discrimination under the ADEA\n"
        "PRAYER FOR RELIEF\n"
    )
    got = {(c.statute, c.theory) for c in extract_claims(t)}
    assert got == {("title_vii", "retaliation"), ("ada", "failure_to_accommodate"),
                   ("title_vii", "hostile_work_environment"), ("adea", "disparate_treatment")}


def test_extract_claims_without_headings_uses_statute_mentions():
    t = "Plaintiff brings this action under the Americans with Disabilities Act. Defendant failed to provide a reasonable accommodation."
    assert [(c.statute, c.theory) for c in extract_claims(t)][0] == ("ada", "failure_to_accommodate")
    t2 = "This action arises under Title VII, 42 U.S.C. § 2000e-3, because Defendant retaliated against her and subjected her to harassment."
    got = {c.theory for c in extract_claims(t2)}
    assert {"retaliation", "hostile_work_environment"} <= got


def test_extract_claims_other_theories():
    t = "COUNT I - Pregnancy Discrimination (Title VII)\nCOUNT II - Religious Accommodation (Title VII)\nCOUNT III - Disparate Impact (Title VII)"
    assert {c.theory for c in extract_claims(t)} == {"pregnancy", "religious_accommodation", "disparate_impact"}


def test_every_claim_theory_is_understood_by_planner_elements():
    for statute, theory in [("title_vii", "retaliation"), ("ada", "failure_to_accommodate"), ("adea", "disparate_treatment"),
                            ("title_vii", "religious_accommodation"), ("title_vii", "pregnancy"),
                            ("title_vii", "hostile_work_environment"), ("title_vii", "disparate_impact")]:
        assert elements.theory_for(statute, theory) is not None


@pytest.mark.parametrize(
    "raw,iso",
    [("March 3, 2026", "2026-03-03"), ("Mar. 3rd, 2026", "2026-03-03"), ("03/04/2026", "2026-03-04"),
     ("3 March 2026", "2026-03-03"), ("2026-03-03", "2026-03-03"), ("March 2026", "2026-03"), ("3/4/26", "2026-03-04"),
     ("February 30, 2026", None), ("not a date", None)],
)
def test_normalize_date(raw, iso):
    assert normalize_date(raw) == iso


def test_extract_key_dates_labels():
    t = (
        "Acme hired Plaintiff on 06/07/2021. On May 19, 2025, Plaintiff complained to HR. "
        "Plaintiff was terminated in July 2025. She filed a charge of discrimination with the EEOC on September 12, 2025. "
        "The EEOC issued a Notice of Right to Sue on 2026-02-10. Dated: March 9, 2026"
    )
    got = {k.label: k.date for k in extract_key_dates(t)}
    assert got == {
        "Hire": "2021-06-07", "Protected complaint": "2025-05-19", "Termination": "2025-07",
        "EEOC charge filed": "2025-09-12", "Right-to-sue letter": "2026-02-10", "Complaint filed": "2026-03-09",
    }


def test_key_dates_two_events_in_one_sentence():
    t = "Plaintiff was hired on January 5, 2020 and terminated on June 1, 2025."
    got = {k.label: k.date for k in extract_key_dates(t)}
    assert got == {"Hire": "2020-01-05", "Termination": "2025-06-01"}


def test_posture_and_facts():
    assert extract_posture("COMPLAINT AND JURY DEMAND ... ") == "Complaint filed; no answer yet"
    assert extract_posture("Defendant's Motion to Dismiss under Rule 12(b)(6) is pending") == "Motion to dismiss pending"
    paras = "\n".join(f"{i}. Fact number {i} " + "word " * 20 for i in range(1, 12))
    text = "FACTUAL ALLEGATIONS\n" + paras + "\nCOUNT I - Retaliation\n"
    facts = extract_facts(text)
    assert facts.startswith("Fact number 1") and "Fact number 5" in facts and len(facts) <= 1200
    assert "COUNT" not in facts and "Fact number 9" not in facts


# -- sample documents -------------------------------------------------------------------------------


def test_ndtex_sample(ndtex):
    rec = extract_case_record(ndtex.text, OfflineModel(), H)
    assert (rec.court_id, rec.circuit) == ("txnd", "5")
    assert rec.court_name == "United States District Court for the Northern District of Texas"
    assert [(p.role, p.name) for p in rec.parties] == [("plaintiff", "[PLAINTIFF]"), ("defendant", "Acme Logistics, Inc.")]
    assert {(c.statute, c.theory) for c in rec.claims} == {("title_vii", "retaliation"), ("title_vii", "disparate_treatment")}
    dates = {k.label: k.date for k in rec.key_dates}
    assert dates["Hire"].startswith("2021") and dates["Protected complaint"] == "2025-05-19"
    assert dates["Termination"] == "2025-07-22" and dates["EEOC charge filed"] == "2025-09-12"
    assert dates["Right-to-sue letter"] == "2026-02-10" and dates["Complaint filed"] == "2026-03-09"
    assert rec.procedural_posture == "Complaint filed; no answer yet"
    assert rec.client_side == "plaintiff"
    assert rec.redaction_count == ndtex.text.count("[")
    assert 0 < len(rec.facts_summary) <= 1200 and "Acme" in rec.facts_summary
    assert "Rivera" not in rec.model_dump_json() and "123-45" not in rec.model_dump_json()
    assert_redacted(rec.facts_summary)


def test_ndcal_scanned_sample_via_ocr(redactor):
    doc = extract_document((SAMPLES / "complaint_ndcal_ada_title7_scanned.pdf").read_bytes(), "s.pdf")
    assert doc.ocr_used
    rec = extract_case_record(redactor.redact(doc.text).text, OfflineModel(), H)
    assert (rec.court_id, rec.circuit) == ("cand", "9")
    assert {(c.statute, c.theory) for c in rec.claims} == {("title_vii", "retaliation"), ("ada", "failure_to_accommodate")}
    dates = {k.label: k.date for k in rec.key_dates}
    assert dates["Termination"] == "2026-03-16"
    assert dates["EEOC charge filed"] == "2026-05-04"
    assert dates["Right-to-sue letter"] == "2026-08-12"
    assert [p.name for p in rec.parties][-1] == "Brightharbor Software, Inc."
    for c in rec.claims:
        assert elements.theory_for(c.statute, c.theory) is not None


def test_adea_text_sample(redactor):
    doc = extract_document((SAMPLES / "complaint_adea.txt").read_bytes(), "adea.txt")
    rec = extract_case_record(redactor.redact(doc.text).text, OfflineModel(), H)
    assert rec.court_id == "nysd"
    assert [(c.statute, c.theory) for c in rec.claims] == [("adea", "disparate_treatment")]
    assert {k.label: k.date for k in rec.key_dates}["Termination"] == "2026-01-15"


# -- LLM path (fake model; never a real API) ----------------------------------------------------------


class FakeLLM(ChatModel):
    provider = "fake"
    is_offline = False

    def __init__(self, reply=None, error: Exception | None = None):
        super().__init__("fake", "fake")
        self.reply, self.error, self.prompts = reply, error, []

    def _complete(self, system, prompt, *, tier, max_tokens):
        raise LLMError("unused")

    def _complete_json(self, system, prompt, schema, *, tier, max_tokens):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        assert schema is LLMCaseExtraction
        return self.reply


def test_llm_path_validates_court_theories_and_dates(ndtex):
    reply = LLMCaseExtraction.model_validate({
        "court_name": "N.D. Tex.", "court_id": "not-a-court",
        "parties": [{"role": "plaintiff", "name": "[PLAINTIFF]"}, {"role": "defendant", "name": "Acme Logistics, Inc."}],
        "claims": [{"statute": "title_vii", "theory": "Retaliation", "description": "Count I"},
                   {"statute": "ada", "theory": "failure_to_accommodate"},
                   {"statute": "title_vii", "theory": "retaliation", "description": "dup"}],
        "key_dates": [{"label": "Termination", "date": "July 22, 2025"}, {"label": "Bad", "date": "sometime"}],
        "procedural_posture": "Complaint filed", "facts_summary": "x" * 2000,
    })
    llm = FakeLLM(reply)
    rec = extract_case_record(ndtex.text, llm, H)
    assert rec.court_id == "txnd" and rec.circuit == "5"  # court_id fixed up through the hierarchy
    assert [(c.statute, c.theory) for c in rec.claims] == [("title_vii", "retaliation"), ("ada", "failure_to_accommodate")]
    assert [(k.label, k.date) for k in rec.key_dates] == [("Termination", "2025-07-22")]
    assert len(rec.facts_summary) == 1200
    assert rec.redaction_count == ndtex.text.count("[")
    assert llm.prompts and "Rivera" not in llm.prompts[0]


def test_llm_gaps_filled_from_rules(ndtex):
    rec = extract_case_record(ndtex.text, FakeLLM(LLMCaseExtraction()), H)
    assert rec.court_id == "txnd" and rec.claims and rec.key_dates and rec.parties


def test_llm_error_falls_back_to_rules(ndtex):
    rec = extract_case_record(ndtex.text, FakeLLM(error=LLMError("boom")), H)
    assert rec.court_id == "txnd" and len(rec.claims) == 2


def test_unredacted_text_never_reaches_llm():
    with pytest.raises(Exception):
        # the ChatModel guard itself refuses; the extractor must not swallow a PII leak silently
        FakeLLM(LLMCaseExtraction()).complete_json("s", "SSN 123-45-6789", LLMCaseExtraction)
