import pytest

from stare.citations.reporters import (
    case_name_similarity,
    normalize_case_name,
    normalize_reporter,
    reporter_key,
)


@pytest.mark.parametrize("raw,want", [
    ("F. 3d", "F.3d"), ("F.3d", "F.3d"), ("F.3d.", "F.3d"), ("F 3d", "F.3d"), ("U. S.", "U.S."), ("U.S.", "U.S."),
    ("S.Ct.", "S. Ct."), ("S. Ct.", "S. Ct."), ("F. Supp. 2d", "F. Supp. 2d"), ("F.Supp.2d", "F. Supp. 2d"),
    ("F. App'x", "F. App'x"), ("Fed. Appx.", "F. App'x"), ("F.Appx.", "F. App'x"), ("WL", "WL"),
])
def test_reporter_normalisation(raw, want):
    assert normalize_reporter(raw) == want


def test_reporter_key_equal_across_spellings():
    assert reporter_key("F. 3d") == reporter_key("F.3d.") == reporter_key("F 3d")


def test_unknown_reporter_passes_through():
    assert normalize_reporter("Zzz. Rptr.") == "Zzz. Rptr."


def test_nassar_abbreviations_match():
    assert case_name_similarity("Univ. of Tex. Sw. Med. Ctr. v. Nassar", "University of Texas Southwestern Medical Center v. Nassar") >= 0.95


def test_noise_words_and_v_variants():
    assert case_name_similarity("Toyota Motor Mfg., Ky., Inc. v. Williams", "Toyota Motor Manufacturing, Kentucky, Inc. v. Williams") >= 0.95
    assert case_name_similarity("McDonnell Douglas Corp. v. Green", "McDonnell Douglas Corporation vs. Green et al.") >= 0.95
    assert case_name_similarity("EEOC v. Abercrombie & Fitch Stores, Inc.", "Equal Employment Opportunity Commission v. Abercrombie & Fitch Stores") >= 0.9


def test_short_name_matches_full_name():
    assert case_name_similarity("Nassar", "University of Texas Southwestern Medical Center v. Nassar") >= 0.9


def test_different_case_at_same_cite_does_not_match():
    # Varghese is invented; a real case sits at that page. Even a shared defendant must not rescue it.
    assert case_name_similarity("Varghese v. China Southern Airlines", "Smith v. China Southern Airlines Co.") < 0.6
    assert case_name_similarity("Varghese v. China Southern Airlines", "Acme Logistics, Inc. v. Doe") < 0.6
    assert case_name_similarity("Miller v. United Airlines, Inc.", "Smith v. Acme Corp") < 0.6


def test_empty_names():
    assert case_name_similarity("", "A v. B") == 0.0


def test_normalize_case_name():
    assert normalize_case_name("Smith v. Jones Co., Inc.") == "smith v jones"
