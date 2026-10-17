import pytest

from stare.citations.parser import extract_citations, sentence_starts


def one(text):
    cs = extract_citations(text)
    assert len(cs) == 1, cs
    return cs[0]


def test_full_case_citation_fields():
    t = "See Varghese v. China Southern Airlines Co., Ltd., 925 F.3d 1339, 1342 (11th Cir. 2019)."
    c = one(t)
    assert c.kind == "case" and c.cite == "925 F.3d 1339"
    assert (c.volume, c.reporter, c.page) == ("925", "F.3d", "1339")
    assert c.case_name == "Varghese v. China Southern Airlines Co., Ltd."
    assert c.year == 2019 and c.court_hint == "11th Cir." and c.pin_cite == "1342"
    assert t[c.span[0]:c.span[1]] == c.raw
    assert c.raw.startswith("Varghese") and c.raw.endswith("2019)")


def test_reporter_variants_are_normalised():
    c = one("Doe v. Roe, 100 F. 3d 5 (5th Cir. 1996).")
    assert c.reporter == "F.3d" and c.cite == "100 F.3d 5"
    c = one("Doe v. Roe, 12 Fed. Appx. 345 (5th Cir. 2001).")
    assert c.reporter == "F. App'x"
    c = one("Doe v. Roe, 133 S.Ct. 2517 (2013).")
    assert c.reporter == "S. Ct."


def test_abbreviated_plaintiff_survives():
    c = one("Univ. of Tex. Sw. Med. Ctr. v. Nassar, 570 U.S. 338, 360 (2013), controls.")
    assert c.case_name == "Univ. of Tex. Sw. Med. Ctr. v. Nassar"
    assert c.pin_cite == "360"


def test_name_does_not_swallow_leading_clause():
    c = one("Under Title VII, Smith v. Jones, 10 F.3d 20 (4th Cir. 1994), applies. ")
    assert c.case_name == "Smith v. Jones"
    c = one("The court held in Estate of Durden v. KLM Royal Dutch Airlines, 99 F.3d 1 (2d Cir. 1996) that x.")
    assert c.case_name == "Estate of Durden v. KLM Royal Dutch Airlines"
    c = one("Toyota Motor Mfg., Ky., Inc. v. Williams, 534 U.S. 184 (2002).")
    assert c.case_name == "Toyota Motor Mfg., Ky., Inc. v. Williams"


def test_previous_sentence_not_included():
    c = one("Courts agree on this point. Smith v. Jones, 10 F.3d 20 (4th Cir. 1994).")
    assert c.case_name == "Smith v. Jones"


def test_no_case_name_bare_cite():
    c = one("The standard appears at 411 U.S. 792.")
    assert c.cite == "411 U.S. 792" and c.case_name == ""


def test_westlaw_cite_extracted():
    c = one("Martinez v. Delta Air Lines, Inc., 2019 WL 4639462 (Tex. App. Sept. 25, 2019).")
    assert c.cite == "2019 WL 4639462" and c.reporter == "WL"
    assert c.case_name == "Martinez v. Delta Air Lines, Inc."
    assert c.year == 2019 and c.court_hint == "Tex. App."


def test_state_neutral_cite_extracted():
    c = one("Shaboon v. Egyptair, 2013 IL App (1st) 111279-U (Ill. App. Ct. 2013).")
    assert c.cite == "2013 IL App (1st) 111279-U"
    assert c.case_name == "Shaboon v. Egyptair" and c.year == 2013


def test_regex_fallback_for_neutral_cites():
    c = one("Doe v. Roe, 2020 OH 1234 (Ohio 2020).")
    assert c.page == "1234" and c.case_name == "Doe v. Roe"


def test_short_form_and_id_resolve_to_antecedent():
    t = ("Univ. of Tex. Sw. Med. Ctr. v. Nassar, 570 U.S. 338, 360 (2013). Later, Nassar, 570 U.S. at 362, "
         "confirms it. Id. at 363.")
    cs = extract_citations(t)
    assert [c.kind for c in cs] == ["case", "short_form", "id"]
    for c in cs[1:]:
        assert c.cite == "570 U.S. 338" or c.page in ("338", "362")
        assert c.volume == "570" and c.case_name == cs[0].case_name
    assert cs[1].pin_cite == "362"
    assert cs[2].pin_cite == "363"


def test_id_without_antecedent_has_no_cite():
    c = one("Id. at 5.")
    assert c.kind == "id" and c.cite == "" and not c.volume


def test_statutes_and_regulations():
    t = "Retaliation is barred by 42 U.S.C. § 2000e-3(a), and 29 C.F.R. § 1630.2(o) defines accommodation; see 29 U.S.C. § 623(a)(1)."
    cs = extract_citations(t)
    assert [c.kind for c in cs] == ["statute", "regulation", "statute"]
    assert cs[0].cite == "42 U.S.C. § 2000e-3" and cs[0].pin_cite == "(a)" and cs[0].page == "2000e-3"
    assert cs[1].cite == "29 C.F.R. § 1630.2" and cs[1].reporter == "C.F.R."
    assert cs[2].cite == "29 U.S.C. § 623"


def test_id_after_statute_points_to_statute():
    cs = extract_citations("Retaliation is barred. 42 U.S.C. § 2000e-3(a). Id.")
    assert cs[-1].kind == "id" and cs[-1].cite == "42 U.S.C. § 2000e-3" and cs[-1].reporter == "U.S.C."


def test_quote_after_citation_in_parenthetical():
    t = 'Smith v. Jones, 10 F.3d 20, 22 (4th Cir. 1994) ("an employer may not retaliate against a worker").'
    assert one(t).quote == "an employer may not retaliate against a worker"


def test_quote_before_citation_curly_quotes():
    t = "The court said “the employer must show a legitimate reason” in Smith v. Jones, 10 F.3d 20 (4th Cir. 1994)."
    assert one(t).quote == "the employer must show a legitimate reason"


def test_quote_in_other_sentence_not_attached():
    t = 'He wrote "this is some unrelated quoted material here." Then, Smith v. Jones, 10 F.3d 20 (4th Cir. 1994), holds otherwise.'
    c = one(t)
    assert c.quote == "" or "unrelated" not in c.quote
    t2 = 'He wrote "this is some unrelated quoted material here" in a memo. Smith v. Jones, 10 F.3d 20 (4th Cir. 1994).'
    assert one(t2).quote == ""


def test_quote_goes_to_nearest_citation():
    t = ('Smith v. Jones, 10 F.3d 20 (4th Cir. 1994) (holding "retaliation is unlawful under the statute"); '
         'Doe v. Roe, 11 F.3d 30 (4th Cir. 1995).')
    a, b = extract_citations(t)
    assert "retaliation" in a.quote and b.quote == ""


def test_scare_quotes_ignored():
    assert one('A "pretext" claim, Smith v. Jones, 10 F.3d 20 (4th Cir. 1994).').quote == ""


def test_spans_are_offsets_in_input():
    t = "Intro text. " + "x " * 30 + "Smith v. Jones, 10 F.3d 20 (4th Cir. 1994). Id. at 21."
    for c in extract_citations(t):
        assert t[c.span[0]:c.span[1]].strip() == c.raw


def test_empty_and_plain_text():
    assert extract_citations("") == []
    assert extract_citations("No citations here, just prose.") == []


def test_sentence_starts_respects_abbreviations():
    t = "See Acme Co. v. Doe, Inc. and J. Smith. Next sentence here. Another one."
    starts = sentence_starts(t)
    assert [t[s:s + 4] for s in starts] == ["See ", "Next", "Anot"]


def test_in_re_case_name():
    assert one("See In re Smith Estate, 10 F.3d 20 (4th Cir. 1994).").case_name == "In re Smith Estate"


def test_quote_belongs_to_the_citation_that_introduces_it():
    from stare.citations.parser import extract_citations

    text = ('In National Railroad Passenger Corp. v. Morgan, 536 U.S. 101 (2002), the court explained: '
            '"An individual must file a charge within the statutory time period." '
            'See Babb v. Wilkie, 589 U.S. 399 (2020).')
    cites = {c.cite: c for c in extract_citations(text)}
    assert cites["536 U.S. 101"].quote.startswith("An individual must file")
    assert cites["589 U.S. 399"].quote == ""



def test_string_citation_case_names_stop_at_semicolons():
    from stare.citations.parser import extract_citations

    text = ("See Varghese v. China Southern Airlines Co., Ltd., 925 F.3d 1339 (11th Cir. 2019); "
            "Shaboon v. Egyptair, 2013 IL App (1st) 111279-U (Ill. App. Ct. 2013); "
            "Miller v. United Airlines, Inc., 174 F.3d 366 (4th Cir. 1999).")
    names = {c.cite: c.case_name for c in extract_citations(text)}
    assert names["2013 IL App (1st) 111279-U"] == "Shaboon v. Egyptair"
    assert names["174 F.3d 366"] == "Miller v. United Airlines, Inc."


@pytest.mark.parametrize("text, name", [
    ("See also Texas Dep't of Cmty. Affairs v. Burdine, 450 U.S. 248 (1981).", "Texas Dep't of Cmty. Affairs v. Burdine"),
    ("See Ass'n of Mexican-Am. Educators v. California, 231 F.3d 572 (9th Cir. 2000).",
     "Ass'n of Mexican-Am. Educators v. California"),
    ("Gen. Dynamics Land Sys., Inc. v. Cline, 540 U.S. 581 (2004).", "Gen. Dynamics Land Sys., Inc. v. Cline"),
])
def test_bluebook_abbreviations_do_not_split_case_names(text, name):
    assert one(text).case_name == name


def test_semicolon_inside_a_parenthetical_does_not_end_the_introducing_citation():
    text = ('In A v. B, 1 U.S. 2 (1990) [1] (Supreme Court; binds every federal court), the court explained: '
            '"The rule is stated here in full." See C v. D, 3 F.3d 4 (9th Cir. 1999) [2] (persuasive).')
    a, c = extract_citations(text)
    assert a.quote == "The rule is stated here in full." and c.quote == ""


def test_markdown_italics_and_short_forms_resolve_to_the_antecedent():
    from stare.citations.parser import extract_citations

    text = ("*University of Texas Southwestern Medical Center v. Nassar*, 570 U.S. 338, 362 (2013). "
            "The Court rejected the motivating-factor test. *Nassar*, 570 U.S. at 352.")
    full, short = extract_citations(text)
    assert full.case_name.endswith("v. Nassar") and "*" not in full.case_name
    assert short.kind == "short_form" and short.cite == "570 U.S. 338" and short.pin_cite == "352"
