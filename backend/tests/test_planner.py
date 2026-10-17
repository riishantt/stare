from stare.intake.elements import THEORIES, theory_for
from stare.intake.planner import draft_plan
from stare.llm import OfflineModel
from stare.schemas import CaseRecord, Claim


def test_every_theory_has_elements_and_queries():
    for theory in THEORIES.values():
        assert theory.elements
        assert all(e.queries for e in theory.elements)


def test_aliases_and_fallback():
    assert theory_for("title_vii", "Retaliation").key == "retaliation"
    assert theory_for("ada", "reasonable accommodation").key == "failure_to_accommodate"
    assert theory_for("adea", "something unusual").key == "disparate_treatment"


def test_plan_for_title_vii_retaliation_and_ada():
    record = CaseRecord(
        court_id="cand",
        court_name="N.D. Cal.",
        claims=[Claim(statute="title_vii", theory="retaliation"), Claim(statute="ada", theory="failure_to_accommodate")],
    )
    plan = draft_plan(record, OfflineModel())
    issues = [i.issue for i in plan.items]
    assert any("retaliation" in i.lower() for i in issues)
    assert any("failure-to-accommodate" in i.lower() for i in issues)
    assert any("EEOC charge" in i or "exhaustion" in i for i in issues)  # procedural item per statute
    assert [i.id for i in plan.items] == [f"P{n}" for n in range(1, len(plan.items) + 1)]
    assert plan.include_adverse and "N.D. Cal." in plan.question
