# STARE evaluation results

Generated 2026-10-20T13:33:46+00:00 with LLM provider `openai_compat:nvidia/nemotron-3-ultra-550b-a55b:free`, embedder `lsa`, reranker `lexical`, on 3 gold questions (0 errors).

LLM calls: 36 succeeded, 7 failed; 3 of 3 memos drafted by the LLM (the others fell back to the offline drafter).

| Metric | Result | Target (Table 29) |
|---|---|---|
| Mata fixture: fabricated citations blocked | 6 of 6 non-exportable (6 blocked, 0 unresolved) | 6 of 6 |
| Unverified citations in exported memos | 0 | 0 |
| Citation accuracy (automated: exists + quote matches) | 1.000 | ≥ 0.94 |
| Hallucination rate (proposed memo citations failing the Firewall) | 0.125 | ≤ 0.02 |
| Retrieval recall@10 | 1.000 | ≥ 0.80 |
| Redaction coverage (auto engine) | 100.0% (27/27) | 100% |
| Redaction coverage (regex-only engine) | 96.3% (26/27) | — |
| Latency, approved plan to memo (p95) | 228.758 s | < 90 s |
| Citation accuracy, reviewed: exists **and supports the statement** (74 citations, [support_review.md](support_review.md)) | 0.986 | ≥ 0.94 |
| Hallucination rate, reviewed: citations that do not support their statement | 0.014 | ≤ 0.02 |
| Baseline comparison: citation accuracy, general-purpose LLM without retrieval (`opencode/beam-free (free general-purpose LLM, no retrieval)`, 100 questions, 563 citations) | 0.979 (STARE 1.000) | STARE higher |
| Baseline accuracy over citations the Firewall could check (5 unresolved excluded) | 0.987 | — |
| Baseline citations blocked as nonexistent or misquoted | 6 of 563 | — |

Notes:
- The automated citation accuracy checks that each citation exists in court records and every quotation matches the opinion; the reviewed rows add whether each authority supports its statement (the Table 29 manual check of a 20-question sample, every verdict listed in support_review.md; validation with practising lawyers is future scope, Section 7.4).
- In offline mode the memo is drafted extractively from verified passages, so the hallucination rate measures the pipeline's guarantees. The baseline rows score a free general-purpose LLM answering the same questions without retrieval (`stare eval baseline --answers`); citations the free CourtListener API could not check (rate limit) are counted as unresolved.

## Per-question results

| Question | recall@10 | memo citations | verified | removed | export violations | latency (s) | missed expected |
|---|---|---|---|---|---|---|---|
| G001 | 1.000 | 13 | 13 | 0 | 0 | 99.456 | — |
| G002 | 1.000 | 10 | 10 | 0 | 0 | 149.933 | — |
| G003 | 1.000 | 19 | 18 | 6 | 0 | 237.516 | — |
