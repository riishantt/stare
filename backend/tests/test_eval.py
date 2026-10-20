"""Evaluation metrics and report: definitions and counting (the evaluation itself is never run by the tests)."""

from __future__ import annotations

import json

from test_agents import FakeFirewall, FakeRetriever

from stare.agents.base import AgentDeps
from stare.agents.memo import MemoAgent, _Draft
from stare.eval import runner
from stare.eval.baseline import score_answers
from stare.eval.runner import QuestionResult, citation_metrics, run_question, write_report
from stare.llm import OfflineModel

GOLD_Q = {"id": "G1", "statute": "title_vii", "theory": "retaliation", "court_id": "txnd",
          "question": "What governs Title VII retaliation?", "facts": "She complained and was fired.",
          "expected_citations": ["570 U.S. 338"]}


def test_baseline_status_counts_sum_to_the_total(session_factory, settings):
    fake = "See Foo v. Bar, 1 F.3d 1 (1st Cir. 2019). Foo v. Bar, 1 F.3d 1 (1st Cir. 2019), again."
    r = score_answers([{"id": "G1", "answer": fake}, {"id": "G2", "answer": "No citations."}], settings)
    assert r["citations"] == 2 and r["unresolved"] == 2  # both occurrences, not one per answer
    assert sum(r["status_counts"].values()) == r["citations"]
    assert r["citation_accuracy_resolved"] is None


def test_hallucination_rate_counts_drafted_citations_per_occurrence(session_factory, settings, monkeypatch):
    deps = AgentDeps(llm=OfflineModel(), session_factory=session_factory, settings=settings)
    deps.__dict__["retriever"] = FakeRetriever()
    deps.__dict__["firewall"] = FakeFirewall()
    draft = _Draft(issue="Retaliation.", conclusion="Done.", application="None.",
                   rule="Causation is but-for. Nassar, 570 U.S. 338 [1]. Fake, 999 F.3d 1 holds X. Fake, 999 F.3d 1 says Y.")
    monkeypatch.setattr(MemoAgent, "_offline_draft", lambda self, *a: draft)
    r = run_question(GOLD_Q, deps)
    assert not r.error
    assert r.drafted_citations == 3 and r.drafted_failed == 2  # the adverse-authority list is not counted
    m = citation_metrics([r])
    assert m["hallucination_rate_drafted"] == 2 / 3


def test_citation_metrics_report_strict_and_lenient_accuracy():
    rs = [QuestionResult("G1", 1.0, memo_citations=10, memo_verified=7, memo_warning=3, removed_from_memo=1,
                         export_violations=0, latency_s=1.0, drafted_citations=8, drafted_failed=1)]
    m = citation_metrics(rs)
    assert m["citation_accuracy_automated"] == 1.0 and m["citation_accuracy_strict"] == 0.7
    assert m["memo_citations_warning"] == 3 and m["hallucination_rate_drafted"] == 1 / 8


def _summary(provider: str) -> dict:
    rs = [QuestionResult("G1", 1.0, 4, 3, 1, 0, 0, 2.0, drafted_citations=4)]
    return {"generated_at": "now", "llm_provider": provider, "embedder": "lsa", "reranker": "lexical", "questions": 1,
            "errors": 0, "retrieval_recall_at_10": 1.0, **citation_metrics(rs), "unverified_in_export": 0,
            "latency_p95_s": 2.0, "latency_mean_s": 2.0,
            "mata": {"fabricated": 6, "exportable": 0, "blocked": 6, "unresolved": 0},
            "redaction": {e: {"coverage": 1.0, "redacted": 1, "total": 1} for e in ("auto", "regex")}}


def test_offline_review_and_baseline_rows_only_in_offline_reports(tmp_path):
    (tmp_path / "support_review.json").write_text(json.dumps(
        {"citations": 10, "states_rule": 9, "pertinent_weaker_quote": 1, "not_supporting": 0}))
    (tmp_path / "baseline.json").write_text(json.dumps(
        {"provider": "free", "questions": 1, "citations": 5, "citation_accuracy_automated": 0.8}))
    offline = write_report({"summary": _summary("offline"), "questions": []}, tmp_path).read_text()
    assert "supports the statement" in offline and "Baseline comparison" in offline
    llm = write_report({"summary": _summary("openai_compat:some-model"), "questions": []}, tmp_path).read_text()
    assert "supports the statement" not in llm and "Baseline comparison" not in llm
    assert "strict" in llm and "drafter wrote" in llm
    assert runner.DRAFTED_FIELDS == ("issue", "rule", "application", "conclusion")
