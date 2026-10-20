"""General-purpose LLM baseline (Table 29): the same questions answered by a model without retrieval,
then every citation in its answer is checked by the Citation Firewall.

Needs a real model provider (STARE_LLM_PROVIDER=anthropic or openai_compat). It refuses to run offline
and is never run by the test suite (zero-cost constraint).
"""

from __future__ import annotations

from stare.citations.firewall import CitationFirewall
from stare.config import Settings, get_settings
from stare.db import get_sessionmaker
from stare.eval.runner import load_gold
from stare.llm import get_llm

_SYSTEM = (
    "You are a US employment-law research assistant. Answer the question in a short research memo and support "
    "every statement of law with full case citations (case name, reporter citation, court and year)."
)


def score_answers(answers: list[dict], settings: Settings | None = None, provider: str = "external") -> dict:
    """Run the Citation Firewall over a general-purpose LLM's answers ({"id", "answer"} per gold question).
    This scores any model, including ones run outside STARE (e.g. a free CLI model), at no cost to STARE."""
    settings = settings or get_settings()
    firewall = CitationFirewall(get_sessionmaker(), settings)
    total = exportable = 0
    rows = []
    statuses: list[str] = []  # one per citation occurrence, the same unit as `total`
    for a in answers:
        checks = firewall.verify_text(a["answer"])
        ok = sum(c.exportable for c in checks)
        total += len(checks)
        exportable += ok
        statuses += [c.status for c in checks]
        rows.append({"id": a["id"], "citations": len(checks), "verified": ok,
                     "statuses": {c.citation.cite: c.status for c in checks}})
    blocked = statuses.count("blocked")
    unresolved = statuses.count("unresolved")
    resolved = total - unresolved
    return {
        "provider": provider,
        "questions": len(answers),
        "citations": total,
        "status_counts": {k: statuses.count(k) for k in ("verified", "warning", "blocked", "unresolved")},
        "citation_accuracy_automated": exportable / total if total else None,
        # unresolved = could not be checked (e.g. the free API rate limit), so also report accuracy over checked ones
        "citation_accuracy_resolved": exportable / resolved if resolved else None,
        "hallucination_rate": (total - exportable) / total if total else None,
        "blocked": blocked,
        "unresolved": unresolved,
        "rows": rows,
    }


def run_baseline(limit: int | None = None, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    llm = get_llm(settings)
    if llm.is_offline:
        raise RuntimeError("the baseline needs an LLM provider; set STARE_LLM_PROVIDER (this costs API credits)")
    firewall = CitationFirewall(get_sessionmaker(), settings)
    total = exportable = 0
    rows = []
    for q in load_gold(limit=limit):
        answer = llm.complete(_SYSTEM, q["question"], tier="main", max_tokens=3000)
        checks = firewall.verify_text(answer)
        ok = sum(c.exportable for c in checks)
        total += len(checks)
        exportable += ok
        rows.append({"id": q["id"], "citations": len(checks), "verified": ok,
                     "statuses": {c.citation.cite: c.status for c in checks}})
    return {
        "provider": llm.name,
        "citation_accuracy_automated": exportable / total if total else None,
        "hallucination_rate": (total - exportable) / total if total else None,
        "cost_usd": round(llm.usage.cost_usd, 4),
        "questions": rows,
    }
