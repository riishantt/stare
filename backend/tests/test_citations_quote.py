import random
import time

from stare.citations.quote import match_quote, normalize, split_fragments

OP = ("The employer’s deci-\nsion was “pretextual.” Under Title VII, the plaintiff must show but-for causation.1 "
      "Courts agree that [t]he burden shifts. A plain—and simple—rule applies.")


def test_normalisation():
    assert normalize("The “Employer’s”   Decision") == "the employers decision"
    assert normalize("deci-\nsion") == "decision"
    assert normalize("[T]he plaintiff") == "the plaintiff"
    assert normalize("rule [emphasis added] applies") == "rule applies"
    assert normalize("causation.1 Courts") == "causation courts"


def test_exact_after_normalisation():
    assert match_quote("the employer's decision was “pretextual”", OP).score == 1.0
    assert match_quote("The plaintiff must show but-for causation.", OP).score == 1.0


def test_bracket_alteration_and_hyphenation():
    assert match_quote("Courts agree that [the] burden shifts", OP).score == 1.0
    assert match_quote("the employer's decision", OP).score == 1.0


def test_ellipsis_fragments_in_order():
    assert match_quote("the plaintiff must show ... Courts agree", OP).score == 1.0
    assert match_quote("the plaintiff must show… burden shifts", OP).score == 1.0
    assert split_fragments("a b c . . . d e f") == ["a b c", "d e f"]
    # out of order fragments are not an exact match
    assert match_quote("Courts agree ... the plaintiff must show", OP).score < 0.9


def test_near_quote_and_misquote():
    near = match_quote("Under Title VII, the plaintiff must show a but-for causation.", OP).score
    assert 0.9 <= near < 1.0
    assert match_quote("the employer never owes any duty whatsoever to anyone at all", OP).score < 0.75


def test_empty_quote_and_text():
    assert match_quote("", OP).score == 1.0
    assert match_quote("something", "").score == 0.0


def test_fast_on_large_opinion():
    rnd = random.Random(1)
    words = ["alpha", "beta", "gamma", "delta", "law", "court", "the", "employee", "claim"]
    big = " ".join(rnd.choice(words) for _ in range(6000))  # about 35k chars
    t = time.time()
    s = match_quote("an invented sentence about airline liability under the Montreal Convention and more words", big).score
    assert time.time() - t < 2.0 and s < 0.8
