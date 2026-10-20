"""Evaluation harness: gold set, Mata fixture, export check, redaction coverage, latency (Section 5.3.7).

Runs every gold question through the real agents (Research -> Precedent -> Opposing Counsel -> Firewall ->
Memo -> memo Firewall) on the local corpus. Automated metrics are computed here; "supports the
statement" for citation accuracy still needs the manual review described in the proposal, so the
automated number is reported as existence + quote fidelity.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from stare.agents.base import AgentDeps
from stare.agents.firewall_agent import FirewallAgent
from stare.agents.memo import MemoAgent
from stare.agents.memo_firewall import MemoFirewallAgent, export_violations
from stare.agents.opposing import OpposingCounselAgent
from stare.agents.precedent import PrecedentAgent
from stare.agents.research import ResearchAgent
from stare.agents.state import dump
from stare.config import REPO_DIR, Settings, get_settings
from stare.db import get_sessionmaker
from stare.eval.metrics import mean, norm_cite, p95, recall_at_k
from stare.intake.planner import draft_plan
from stare.llm import get_llm
from stare.schemas import Authority, CaseRecord, Claim, Memo

GOLD = REPO_DIR / "data" / "eval" / "gold.jsonl"
MATA = REPO_DIR / "data" / "eval" / "mata_citations.json"
PII = REPO_DIR / "data" / "samples" / "pii_seeded"
OUT_DIR = REPO_DIR / "docs" / "evaluation"


@dataclass
class QuestionResult:
    id: str
    recall_at_10: float | None
    memo_citations: int
    memo_verified: int
    memo_warning: int
    removed_from_memo: int
    export_violations: int
    latency_s: float
    found_expected: list[str] = field(default_factory=list)
    missed_expected: list[str] = field(default_factory=list)
    memo_drafted_by: str = ""
    error: str = ""


def load_gold(path: Path = GOLD, limit: int | None = None) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return rows[:limit] if limit else rows


def run_question(q: dict, deps: AgentDeps) -> QuestionResult:
    record = CaseRecord(
        court_id=q.get("court_id"), court_name=q.get("court_id"),
        circuit=deps.hierarchy.circuit_of(q.get("court_id")),
        claims=[Claim(statute=q["statute"], theory=q["theory"])],
        facts_summary=q.get("facts") or q["question"],
    )
    plan = draft_plan(record, deps.llm)
    plan.question = q["question"]
    state: dict = {"run_id": 0, "case_record": dump(record), "plan": dump(plan), "redacted_text": q.get("facts") or q["question"]}
    t0 = time.perf_counter()
    try:
        for agent in (ResearchAgent, PrecedentAgent, OpposingCounselAgent, FirewallAgent):
            state |= agent(deps).run(state)
            while agent is FirewallAgent and state.get("retry_research"):
                for again in (ResearchAgent, PrecedentAgent, OpposingCounselAgent, FirewallAgent):
                    state |= again(deps).run(state)
        state |= MemoAgent(deps).run(state)
        state |= MemoFirewallAgent(deps).run(state)
    except Exception as exc:  # one failing question must not abort the evaluation
        return QuestionResult(q["id"], None, 0, 0, 0, 0, 0, time.perf_counter() - t0, error=f"{type(exc).__name__}: {exc}")
    latency = time.perf_counter() - t0

    ranked = PrecedentAgent(deps).rank(
        [Authority.model_validate(a) for a in state.get("candidates", [])],
        record.court_id,
    )
    ranked_cites = [a.citation for a in ranked]
    expected = q.get("expected_citations", [])
    top = {norm_cite(c) for c in ranked_cites[:10]}
    memo = Memo.model_validate(state["memo"])
    memo_checks = [c for c in state.get("checks", []) if c.get("phase") == "memo"]
    return QuestionResult(
        id=q["id"],
        recall_at_10=recall_at_k(ranked_cites, expected),
        memo_citations=len(memo_checks),
        memo_verified=sum(c["status"] == "verified" for c in memo_checks),
        memo_warning=sum(c["status"] == "warning" for c in memo_checks),
        removed_from_memo=sum("removed from the memo" in r for r in memo.removed_citations),
        export_violations=len(export_violations(memo, deps.firewall)),
        latency_s=round(latency, 3),
        found_expected=[e for e in expected if norm_cite(e) in top],
        missed_expected=[e for e in expected if norm_cite(e) not in top],
        memo_drafted_by=memo.generated_by,
    )


def mata_test(deps: AgentDeps) -> dict:
    data = json.loads(MATA.read_text())
    fakes = [c for c in data["citations"] if c.get("mata")]
    text = " ".join(f"See {c['citation']}." for c in fakes)
    checks = deps.firewall.verify_text(text)
    statuses = {c.citation.cite: c.status for c in checks}
    return {
        "fabricated": len(fakes),
        "extracted": len(checks),
        "blocked": sum(s == "blocked" for s in statuses.values()),
        "unresolved": sum(s == "unresolved" for s in statuses.values()),
        "exportable": sum(c.exportable for c in checks),
        "statuses": statuses,
        "passed": len(checks) == len(fakes) and not any(c.exportable for c in checks),
    }


def redaction_coverage() -> dict:
    from stare.intake.redactor import PIIRedactor

    out = {}
    for engine in ("auto", "regex"):
        redactor = PIIRedactor(engine=engine)
        total = hit = 0
        for f in sorted(PII.glob("*.json")):
            item = json.loads(f.read_text())
            red = redactor.redact(item["text"]).text
            total += len(item["pii"])
            hit += sum(p not in red for p in item["pii"])
        out[engine] = {"redacted": hit, "total": total, "coverage": hit / total if total else None}
    return out


def evaluate(limit: int | None = None, settings: Settings | None = None, say=lambda msg: None) -> dict:
    settings = settings or get_settings()
    deps = AgentDeps(llm=get_llm(settings), session_factory=get_sessionmaker(), settings=settings)
    gold = load_gold(limit=limit)
    results = []
    for q in gold:
        results.append(run_question(q, deps))
        r = results[-1]
        say(f"{r.id} recall@10={r.recall_at_10} cited={r.memo_citations} verified={r.memo_verified} "
            f"violations={r.export_violations} {r.latency_s:.1f}s {r.error}")
    ok = [r for r in results if not r.error]
    cited = sum(r.memo_citations for r in ok)
    verified = sum(r.memo_verified + r.memo_warning for r in ok)
    proposed = cited + sum(r.removed_from_memo for r in ok)
    latencies = [r.latency_s for r in ok]
    summary = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "llm_provider": deps.llm.name,
        "llm_calls": deps.llm.usage.calls,
        "llm_failures": deps.llm.usage.failures,
        "llm_retries": deps.llm.usage.retries,
        "llm_failure_reasons": deps.llm.usage.failure_reasons,
        "memos_drafted_by_llm": sum(not r.memo_drafted_by.startswith("offline") for r in ok),
        "embedder": settings.embedder,
        "reranker": settings.reranker,
        "questions": len(gold),
        "errors": len(results) - len(ok),
        "retrieval_recall_at_10": mean([r.recall_at_10 for r in ok]),
        "citation_accuracy_automated": verified / cited if cited else None,
        "hallucination_rate": (proposed - verified) / proposed if proposed else 0.0,
        "unverified_in_export": sum(r.export_violations for r in ok),
        "latency_p95_s": p95(latencies),
        "latency_mean_s": mean(latencies),
        "mata": mata_test(deps),
        "redaction": redaction_coverage(),
        "targets": {
            "citation_accuracy": ">= 0.94", "hallucination_rate": "<= 0.02", "mata": "6 of 6",
            "unverified_in_export": "0", "recall_at_10": ">= 0.80", "redaction": "100%", "latency_p95_s": "< 90",
        },
    }
    return {"summary": summary, "questions": [asdict(r) for r in results]}


def _support_rows(out_dir: Path) -> list[str]:
    """Manual (AI-assisted) review of whether cited authorities support their statements (support_review.md)."""
    path = out_dir / "support_review.json"
    if not path.exists():
        return []
    r = json.loads(path.read_text())
    n = r["citations"]
    ok = r["states_rule"] + r["pertinent_weaker_quote"]
    return [
        f"| Citation accuracy, reviewed: exists **and supports the statement** ({n} citations, [support_review.md](support_review.md)) "
        f"| {ok / n:.3f} | ≥ 0.94 |",
        f"| Hallucination rate, reviewed: citations that do not support their statement | {r['not_supporting'] / n:.3f} | ≤ 0.02 |",
    ]


def _baseline_rows(out_dir: Path, s: dict, fmt) -> list[str]:
    """Baseline comparison (Table 29): a general-purpose LLM answering the same questions without retrieval,
    its citations checked by the same Firewall. Present only after `stare eval baseline` has been run."""
    path = out_dir / "baseline.json"
    if not path.exists():
        return []
    b = json.loads(path.read_text())
    return [
        f"| Baseline comparison: citation accuracy, general-purpose LLM without retrieval (`{b['provider']}`, "
        f"{b['questions']} questions, {b['citations']} citations) | {fmt(b['citation_accuracy_automated'])} "
        f"(STARE {fmt(s['citation_accuracy_automated'])}) | STARE higher |",
        f"| Baseline accuracy over citations the Firewall could check ({b.get('unresolved', 0)} unresolved excluded) | "
        f"{fmt(b.get('citation_accuracy_resolved'))} | — |",
        f"| Baseline citations blocked as nonexistent or misquoted | {b.get('blocked', 0)} of {b['citations']} | — |",
    ]


def write_report(result: dict, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(result, indent=2, default=str))
    s = result["summary"]

    def fmt(v, pct=False):
        if v is None:
            return "n/a"
        return f"{v:.1%}" if pct else (f"{v:.3f}" if isinstance(v, float) else str(v))

    red = s["redaction"]
    lines = [
        "# STARE evaluation results",
        "",
        f"Generated {s['generated_at']} with LLM provider `{s['llm_provider']}`, embedder `{s['embedder']}`, "
        f"reranker `{s['reranker']}`, on {s['questions']} gold questions ({s['errors']} errors).",
        *(["", f"LLM calls: {s.get('llm_calls', 0)} answered, {s.get('llm_failures', 0)} failed, "
               f"{s.get('llm_retries', 0)} retried after an unusable JSON reply; "
               f"{s.get('memos_drafted_by_llm', 0)} of {s['questions'] - s['errors']} memos drafted by the LLM "
               "(the others fell back to the offline drafter)."]
          if not s["llm_provider"].startswith("offline") else []),
        "",
        "| Metric | Result | Target (Table 29) |",
        "|---|---|---|",
        f"| Mata fixture: fabricated citations blocked | {s['mata']['fabricated'] - s['mata']['exportable']} of {s['mata']['fabricated']} non-exportable "
        f"({s['mata']['blocked']} blocked, {s['mata']['unresolved']} unresolved) | 6 of 6 |",
        f"| Unverified citations in exported memos | {s['unverified_in_export']} | 0 |",
        f"| Citation accuracy (automated: exists + quote matches) | {fmt(s['citation_accuracy_automated'])} | ≥ 0.94 |",
        f"| Hallucination rate (proposed memo citations failing the Firewall) | {fmt(s['hallucination_rate'])} | ≤ 0.02 |",
        f"| Retrieval recall@10 | {fmt(s['retrieval_recall_at_10'])} | ≥ 0.80 |",
        f"| Redaction coverage (auto engine) | {fmt(red['auto']['coverage'], True)} ({red['auto']['redacted']}/{red['auto']['total']}) | 100% |",
        f"| Redaction coverage (regex-only engine) | {fmt(red['regex']['coverage'], True)} ({red['regex']['redacted']}/{red['regex']['total']}) | — |",
        f"| Latency, approved plan to memo (p95) | {fmt(s['latency_p95_s'])} s | < 90 s |",
        *_support_rows(out_dir),
        *_baseline_rows(out_dir, s, fmt),
        "",
        "Notes:",
        "- The automated citation accuracy checks that each citation exists in court records and every quotation matches the "
        "opinion; the reviewed rows add whether each authority supports its statement (the Table 29 manual check of a 20-question "
        "sample, every verdict listed in support_review.md; validation with practising lawyers is future scope, Section 7.4).",
        "- In offline mode the memo is drafted extractively from verified passages, so the hallucination rate measures the "
        "pipeline's guarantees. The baseline rows score a free general-purpose LLM answering the same questions without "
        "retrieval (`stare eval baseline --answers`); citations the free CourtListener API could not check (rate limit) "
        "are counted as unresolved.",
        "",
        "## Per-question results",
        "",
        "| Question | recall@10 | memo citations | verified | removed | export violations | latency (s) | missed expected |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for q in result["questions"]:
        lines.append(
            f"| {q['id']} | {fmt(q['recall_at_10'])} | {q['memo_citations']} | {q['memo_verified']} | {q['removed_from_memo']} | "
            f"{q['export_violations']} | {q['latency_s']} | {', '.join(q['missed_expected']) or q['error'] or '—'} |"
        )
    path = out_dir / "results.md"
    path.write_text("\n".join(lines) + "\n")
    return path
