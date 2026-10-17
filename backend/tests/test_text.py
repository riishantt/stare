from stare.text import split_sentences


def test_does_not_split_on_reporter_abbreviations():
    text = ("In Burlington N. & S. F. R. Co. v. White, 548 U. S. 53 (2006), we held that the provision is broad. "
            "The Court relied on McDonnell Douglas Corp. v. Green. Plaintiffs must show but-for causation.")
    assert split_sentences(text) == [
        "In Burlington N. & S. F. R. Co. v. White, 548 U. S. 53 (2006), we held that the provision is broad.",
        "The Court relied on McDonnell Douglas Corp. v. Green.",
        "Plaintiffs must show but-for causation.",
    ]


def test_splits_before_quotes_and_keeps_lowercase_continuations():
    text = 'The rule is settled. "A plaintiff must prove it." See id. at 5. it continues here.'
    assert split_sentences(text) == ["The rule is settled.", '"A plaintiff must prove it."', "See id. at 5. it continues here."]


def test_opinion_parts():
    from stare.text import majority_text, part_at, part_marker

    text = "The court holds X.\n\n" + part_marker("dissent", "Justice Thomas") + "\nI would hold Y.\n\n" + \
        part_marker("concurring-in-part-and-dissenting-in-part") + "\nPartly."
    assert majority_text(text) == "The court holds X.\n\n"
    assert part_at(text, 3) == "majority"
    assert part_at(text, text.index("I would")) == "dissent"
    assert part_at(text, text.index("Partly")) == "separate"


def test_mark_separate_opinions_inside_majority():
    from stare.text import majority_text, mark_separate_opinions, part_at

    text = ("We hold that but-for causation applies.\nIt is so ordered.\n"
            "Justice GINSBURG, with whom Justice BREYER joins, dissenting.\nI would apply motivating factor.")
    marked = mark_separate_opinions(text)
    assert "motivating factor" not in majority_text(marked)
    assert part_at(marked, marked.index("I would")) == "dissent"


def test_strip_syllabus():
    from stare.text import strip_syllabus

    text = "Syllabus\nHeld: transfer needs some harm.\n\nKagan, J., delivered the opinion of the Court.\n\nThe opinion begins."
    assert strip_syllabus(text) == "The opinion begins."
    assert strip_syllabus("No syllabus here at the start? fine") .startswith("No")
