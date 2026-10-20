# STARE evaluation results

Generated 2026-10-20T20:34:56+00:00 with LLM provider `openai_compat:nvidia/nemotron-3-ultra-550b-a55b:free`, embedder `lsa`, reranker `lexical`, on 20 gold questions (0 errors).

LLM calls: 218 succeeded, 61 failed; 19 of 20 memos drafted by the LLM (the others fell back to the offline drafter).

| Metric | Result | Target (Table 29) |
|---|---|---|
| Mata fixture: fabricated citations blocked | 6 of 6 non-exportable (6 blocked, 0 unresolved) | 6 of 6 |
| Unverified citations in exported memos | 0 | 0 |
| Citation accuracy (automated: exists + quote matches) | 1.000 | ≥ 0.94 |
| Hallucination rate (proposed memo citations failing the Firewall) | 0.079 | ≤ 0.02 |
| Retrieval recall@10 | 0.850 | ≥ 0.80 |
| Redaction coverage (auto engine) | 100.0% (27/27) | 100% |
| Redaction coverage (regex-only engine) | 96.3% (26/27) | — |
| Latency, approved plan to memo (p95) | 238.955 s | < 90 s |
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
| G001 | 1.000 | 15 | 15 | 0 | 0 | 273.679 | — |
| G002 | 1.000 | 13 | 12 | 2 | 0 | 216.598 | — |
| G003 | 1.000 | 24 | 23 | 2 | 0 | 124.115 | — |
| G004 | 1.000 | 19 | 17 | 0 | 0 | 182.192 | — |
| G005 | 1.000 | 13 | 13 | 2 | 0 | 106.129 | — |
| G006 | 1.000 | 16 | 15 | 1 | 0 | 128.255 | — |
| G007 | 1.000 | 27 | 21 | 2 | 0 | 122.469 | — |
| G008 | 1.000 | 10 | 10 | 2 | 0 | 127.369 | — |
| G009 | 1.000 | 14 | 14 | 1 | 0 | 57.908 | — |
| G010 | 1.000 | 31 | 31 | 0 | 0 | 159.089 | — |
| G011 | 1.000 | 11 | 11 | 1 | 0 | 151.409 | — |
| G012 | 0.000 | 10 | 9 | 1 | 0 | 148.509 | 492 F.3d 551, 42 U.S.C. § 2000e-3 |
| G013 | 1.000 | 25 | 18 | 1 | 0 | 151.404 | — |
| G014 | 1.000 | 20 | 18 | 2 | 0 | 129.845 | — |
| G015 | 1.000 | 11 | 11 | 2 | 0 | 237.127 | — |
| G016 | 0.500 | 13 | 11 | 0 | 0 | 81.414 | 281 F.3d 1054 |
| G017 | 1.000 | 15 | 14 | 3 | 0 | 92.433 | — |
| G018 | 0.000 | 19 | 16 | 0 | 0 | 153.498 | 532 U.S. 268 |
| G019 | 1.000 | 12 | 11 | 0 | 0 | 105.816 | — |
| G020 | 0.500 | 18 | 16 | 7 | 0 | 173.103 | 530 U.S. 133 |
