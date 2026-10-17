"""PII redaction (stare.intake.redactor): coverage (NFR-03), over-redaction guards, consistency."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stare.intake.redactor import PIIRedactor
from stare.llm import assert_redacted

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"
SEEDED = [json.loads(p.read_text()) for p in sorted((SAMPLES / "pii_seeded").glob("*.json"))]


@pytest.fixture(scope="module")
def regex_engine() -> PIIRedactor:
    return PIIRedactor("regex")


@pytest.fixture(scope="module")
def auto_engine() -> PIIRedactor:
    """One Presidio analyzer for the whole module (the spaCy model loads once per process)."""
    return PIIRedactor("auto")


def _coverage(engine: PIIRedactor) -> tuple[int, int, list[str]]:
    total, missed = 0, []
    for case in SEEDED:
        out = engine.redact(case["text"]).text
        for pii in case["pii"]:
            total += 1
            if pii in out:
                missed.append(pii)
    return total - len(missed), total, missed


def test_seeded_set_is_large_enough():
    assert len(SEEDED) >= 10


def test_auto_engine_uses_presidio_and_reaches_full_coverage(auto_engine):
    assert auto_engine.engine == "presidio"
    ok, total, missed = _coverage(auto_engine)
    print(f"auto coverage {ok}/{total}")
    assert not missed, f"unredacted PII: {len(missed)} of {total}"


def test_regex_engine_coverage_is_reported(regex_engine):
    ok, total, missed = _coverage(regex_engine)
    print(f"regex coverage {ok}/{total} missed={len(missed)}")
    # Regex-only must catch every structured identifier; only uncued free-text names may slip through.
    structured_missed = [m for m in missed if any(ch.isdigit() or ch == "@" for ch in m)]
    assert not structured_missed
    assert ok / total >= 0.9


def test_structured_identifiers(regex_engine):
    text = (
        "SSN 123-45-6789; mail a.b@x.org; call (415) 555-0101; DOB: 02/03/1980; "
        "ZIP 94107-1234; driver's license no. D1234567; card 4111-1111-1111-1111; "
        "employee ID: 99120; 12 Oak Street, Austin, TX 78701."
    )
    res = regex_engine.redact(text)
    for raw in ("123-45-6789", "a.b@x.org", "555-0101", "02/03/1980", "94107-1234", "D1234567", "4111", "99120", "12 Oak Street"):
        assert raw not in res.text
    types = {e.entity_type for e in res.entities}
    assert {"US_SSN", "EMAIL_ADDRESS", "PHONE_NUMBER", "DATE_OF_BIRTH", "US_DRIVER_LICENSE", "CREDIT_CARD",
            "ID_NUMBER", "STREET_ADDRESS"} <= types
    assert_redacted(res.text)


def test_no_over_redaction_of_legal_terms(auto_engine):
    text = (
        "UNITED STATES DISTRICT COURT FOR THE NORTHERN DISTRICT OF TEXAS, DALLAS DIVISION. "
        "Plaintiff sued Acme Logistics, Inc. under Title VII of the Civil Rights Act of 1964, 42 U.S.C. § 2000e-3(a), "
        "the Americans with Disabilities Act and the Age Discrimination in Employment Act after an Equal Employment "
        "Opportunity Commission charge. Judge Reed O'Connor applied McDonnell Douglas Corp. v. Green, 411 U.S. 792 "
        "(1973), and Burlington Northern & Santa Fe Railway Co. v. White, 548 U.S. 53 (2006), in the Fifth Circuit."
    )
    for engine in (auto_engine, PIIRedactor("regex")):
        out = engine.redact(text).text
        for keep in ("NORTHERN DISTRICT OF TEXAS", "DALLAS DIVISION", "Acme Logistics, Inc.", "Title VII",
                     "Civil Rights Act of 1964", "42 U.S.C. § 2000e-3(a)", "Americans with Disabilities Act",
                     "Age Discrimination in Employment Act", "Equal Employment Opportunity Commission",
                     "Reed O'Connor", "McDonnell Douglas Corp. v. Green", "Burlington Northern", "Fifth Circuit"):
            assert keep in out, f"{keep!r} was wrongly redacted by {engine.engine}: {out}"


def test_seeded_keep_lists_survive(auto_engine):
    for case in SEEDED:
        out = auto_engine.redact(case["text"]).text
        for keep in case.get("keep", []):
            assert keep in out


def test_placeholders_consistent_for_same_entity(auto_engine):
    text = (
        "Plaintiff Maria Rivera complained to her supervisor Gregory Haldane. Ms. Rivera was fired. "
        "Mr. Haldane denied it. Maria Rivera emailed maria@x.org and later maria@x.org again; "
        "she phoned 214-555-0100 and 214-555-0111."
    )
    res = auto_engine.redact(text)
    out = res.text
    assert out.count("[PLAINTIFF]") == 3  # Maria Rivera, Ms. Rivera, Maria Rivera
    assert out.count("[PERSON_1]") == 2  # Gregory Haldane, Mr. Haldane
    assert "[PERSON_2]" not in out
    assert out.count("[EMAIL_1]") == 2 and "[EMAIL_2]" not in out
    assert "[PHONE_1]" in out and "[PHONE_2]" in out


def test_surname_first_then_full_name_share_placeholder(auto_engine):
    out = auto_engine.redact("Ms. Okonkwo-Reyes sued. Later, Dana Okonkwo-Reyes testified; Mr. Pratt agreed.").text
    assert out.count("[PERSON_1]") == 2 and "[PERSON_2]" in out


def test_entity_offsets_refer_to_redacted_text(auto_engine):
    text = "Contact Gregory Haldane at g.haldane@x.org or 214-555-0100 (SSN 123-45-6789)."
    res = auto_engine.redact(text)
    assert res.entities
    for e in res.entities:
        assert res.text[e.start:e.end] == e.placeholder
    assert [e.start for e in res.entities] == sorted(e.start for e in res.entities)
    assert res.count == len(res.entities)


def test_keep_parameter(regex_engine):
    res = regex_engine.redact("Write to a@b.org or c@d.org", keep={"a@b.org"})
    assert "a@b.org" in res.text and "c@d.org" not in res.text
    res = regex_engine.redact("Write to a@b.org, SSN 123-45-6789", keep={"EMAIL_ADDRESS"})
    assert "a@b.org" in res.text and "123-45-6789" not in res.text


def test_dates_ages_and_city_of_work_survive(auto_engine):
    out = auto_engine.redact("On March 3, 2026, Plaintiff, age 58, was fired from the Dallas, Texas warehouse.").text
    assert "March 3, 2026" in out and "age 58" in out and "Dallas, Texas" in out


def test_residence_city_is_redacted(auto_engine):
    out = auto_engine.redact("Plaintiff resides in Plano, Texas and works in Dallas.").text
    assert "Plano" not in out and "Dallas" in out


@pytest.mark.parametrize("name", ["complaint_ndtex_title7_retaliation.pdf", "complaint_adea.txt"])
def test_sample_complaints_pass_prompt_guard(auto_engine, name):
    from stare.intake.pdf_reader import extract_document

    doc = extract_document((SAMPLES / name).read_bytes(), name)
    res = auto_engine.redact(doc.text)
    assert_redacted(res.text)
    for raw in ("123-45-6789", "examplemail.com", "555-0142", "Willow Creek", "Rivera", "Haldane", "Brennan", "Harbor View"):
        assert raw not in res.text
    assert "Acme Logistics, Inc." in res.text or "NORTHBRIDGE" in res.text
    assert "NORTHERN DISTRICT OF TEXAS" in res.text or "SOUTHERN DISTRICT OF NEW YORK" in res.text


def test_empty_text_and_bad_engine():
    assert PIIRedactor("regex").redact("").text == ""
    with pytest.raises(ValueError):
        PIIRedactor("nope")  # type: ignore[arg-type]


def test_cited_case_captions_are_not_redacted_but_parties_are():
    from stare.intake.redactor import PIIRedactor

    text = ("Plaintiff Maria Rivera relies on Martinez v. Delta Air Lines, Inc., 2019 WL 4639462 (Tex. App. 2019). "
            "Rivera v. Acme Logistics is this case.")
    out = PIIRedactor(engine="regex").redact(text).text
    assert "Martinez v. Delta Air Lines" in out
    assert "Maria Rivera" not in out and "Rivera v. Acme" not in out


@pytest.mark.parametrize("text, name", [
    ("My supervisor John Smith and a co-worker mocked me.", "John Smith"),  # "co-" is not a company suffix
    ("Robert Jones was the foreman. Jones and his co-workers laughed.", "Jones"),
    ("Plaintiff told the court that Karen Miller called her slurs in the United States.", "Karen Miller"),
    ("Plaintiff complained to Linda Brown Office Manager about the comments.", "Linda Brown"),
])
def test_names_near_legal_vocabulary_are_still_redacted(auto_engine, text, name):
    assert name not in auto_engine.redact(text).text


def test_person_sharing_a_famous_case_name_is_redacted(auto_engine):
    out = auto_engine.redact("My supervisor John Hicks called me old. Hicks fired me. Ms. Hubbard ignored it.").text
    assert "Hicks" not in out and "Hubbard" not in out
    cited = "Under Faragher, see St. Mary's Honor Center v. Hicks, 509 U.S. 502 (1993)."
    assert auto_engine.redact(cited).text == cited


def test_caption_lines_stay_protected(regex_engine):
    text = "IN THE UNITED STATES DISTRICT COURT\nFOR THE NORTHERN DISTRICT OF TEXAS\n\nMARIA RIVERA,\n  Plaintiff,"
    out = regex_engine.redact(text).text
    assert out.startswith("IN THE UNITED STATES DISTRICT COURT\nFOR THE NORTHERN DISTRICT OF TEXAS")
    assert "MARIA RIVERA" not in out
