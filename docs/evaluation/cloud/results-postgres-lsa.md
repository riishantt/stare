# STARE evaluation results

Generated 2026-10-17T15:18:08+00:00 with LLM provider `offline`, embedder `lsa`, reranker `lexical`, on 100 gold questions (0 errors).

| Metric | Result | Target (Table 29) |
|---|---|---|
| Mata fixture: fabricated citations blocked | 6 of 6 non-exportable (3 blocked, 3 unresolved) | 6 of 6 |
| Unverified citations in exported memos | 0 | 0 |
| Citation accuracy (automated: exists + quote matches) | 1.000 | ≥ 0.94 |
| Hallucination rate (proposed memo citations failing the Firewall) | 0.000 | ≤ 0.02 |
| Retrieval recall@10 | 0.865 | ≥ 0.80 |
| Redaction coverage (auto engine) | 100.0% (27/27) | 100% |
| Redaction coverage (regex-only engine) | 96.3% (26/27) | — |
| Latency, approved plan to memo (p95) | 2.732 s | < 90 s |
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
| G001 | 1.000 | 16 | 16 | 0 | 0 | 3.99 | — |
| G002 | 1.000 | 16 | 16 | 0 | 0 | 2.433 | — |
| G003 | 1.000 | 16 | 16 | 0 | 0 | 2.097 | — |
| G004 | 1.000 | 17 | 17 | 0 | 0 | 2.257 | — |
| G005 | 1.000 | 16 | 16 | 0 | 0 | 2.009 | — |
| G006 | 1.000 | 16 | 16 | 0 | 0 | 2.218 | — |
| G007 | 1.000 | 16 | 16 | 0 | 0 | 2.088 | — |
| G008 | 0.000 | 17 | 17 | 0 | 0 | 2.198 | 532 U.S. 268 |
| G009 | 1.000 | 18 | 18 | 0 | 0 | 2.219 | — |
| G010 | 1.000 | 16 | 16 | 0 | 0 | 2.099 | — |
| G011 | 1.000 | 18 | 18 | 0 | 0 | 2.142 | — |
| G012 | 0.500 | 16 | 16 | 0 | 0 | 2.401 | 492 F.3d 551 |
| G013 | 1.000 | 16 | 16 | 0 | 0 | 2.121 | — |
| G014 | 1.000 | 16 | 16 | 0 | 0 | 2.102 | — |
| G015 | 1.000 | 16 | 16 | 0 | 0 | 2.285 | — |
| G016 | 0.500 | 16 | 16 | 0 | 0 | 2.19 | 281 F.3d 1054 |
| G017 | 1.000 | 17 | 17 | 0 | 0 | 2.261 | — |
| G018 | 0.000 | 16 | 16 | 0 | 0 | 2.125 | 532 U.S. 268 |
| G019 | 1.000 | 18 | 18 | 0 | 0 | 2.377 | — |
| G020 | 0.500 | 16 | 16 | 0 | 0 | 2.113 | 530 U.S. 133 |
| G021 | 0.000 | 12 | 11 | 0 | 0 | 2.427 | 411 U.S. 792 |
| G022 | 0.500 | 13 | 13 | 0 | 0 | 2.307 | 450 U.S. 248 |
| G023 | 1.000 | 12 | 11 | 0 | 0 | 2.658 | — |
| G024 | 1.000 | 12 | 11 | 0 | 0 | 2.44 | — |
| G025 | 1.000 | 12 | 11 | 0 | 0 | 2.389 | — |
| G026 | 1.000 | 13 | 12 | 0 | 0 | 2.181 | — |
| G027 | 1.000 | 14 | 13 | 0 | 0 | 2.456 | — |
| G028 | 0.500 | 12 | 11 | 0 | 0 | 2.497 | 490 U.S. 228 |
| G029 | 1.000 | 14 | 14 | 0 | 0 | 2.373 | — |
| G030 | 1.000 | 13 | 12 | 0 | 0 | 2.226 | — |
| G031 | 1.000 | 14 | 13 | 0 | 0 | 2.593 | — |
| G032 | 1.000 | 12 | 12 | 0 | 0 | 2.376 | — |
| G033 | 1.000 | 13 | 12 | 0 | 0 | 2.418 | — |
| G034 | 1.000 | 13 | 12 | 0 | 0 | 2.355 | — |
| G035 | 1.000 | 13 | 12 | 0 | 0 | 2.353 | — |
| G036 | 0.500 | 13 | 12 | 0 | 0 | 2.537 | 492 F.3d 551 |
| G037 | 1.000 | 14 | 13 | 0 | 0 | 2.428 | — |
| G038 | 1.000 | 12 | 11 | 0 | 0 | 2.311 | — |
| G039 | 0.000 | 12 | 12 | 0 | 0 | 2.206 | 401 U.S. 424 |
| G040 | 1.000 | 14 | 13 | 0 | 0 | 2.415 | — |
| G041 | 0.000 | 12 | 12 | 0 | 0 | 2.335 | 411 U.S. 792, 349 F.3d 634 |
| G042 | 1.000 | 13 | 12 | 0 | 0 | 2.256 | — |
| G043 | 1.000 | 12 | 12 | 0 | 0 | 2.29 | — |
| G044 | 1.000 | 13 | 12 | 0 | 0 | 2.437 | — |
| G045 | 1.000 | 13 | 13 | 0 | 0 | 2.931 | — |
| G046 | 1.000 | 13 | 13 | 0 | 0 | 2.662 | — |
| G047 | 1.000 | 13 | 13 | 0 | 0 | 2.598 | — |
| G048 | 1.000 | 14 | 14 | 0 | 0 | 3.032 | — |
| G049 | 1.000 | 12 | 12 | 0 | 0 | 2.576 | — |
| G050 | 0.500 | 13 | 13 | 0 | 0 | 2.447 | 524 U.S. 742 |
| G051 | 1.000 | 13 | 13 | 0 | 0 | 2.638 | — |
| G052 | 1.000 | 12 | 12 | 0 | 0 | 2.503 | — |
| G053 | 0.000 | 13 | 13 | 0 | 0 | 2.658 | 524 U.S. 775, 532 U.S. 268 |
| G054 | 1.000 | 13 | 13 | 0 | 0 | 2.919 | — |
| G055 | 1.000 | 13 | 13 | 0 | 0 | 2.761 | — |
| G056 | 0.500 | 14 | 14 | 0 | 0 | 2.637 | 419 F.3d 885 |
| G057 | 0.500 | 12 | 12 | 0 | 0 | 2.731 | 510 U.S. 17 |
| G058 | 1.000 | 13 | 13 | 0 | 0 | 2.685 | — |
| G059 | 1.000 | 14 | 14 | 0 | 0 | 2.634 | — |
| G060 | 1.000 | 12 | 12 | 0 | 0 | 2.479 | — |
| G061 | 1.000 | 13 | 13 | 0 | 0 | 1.445 | — |
| G062 | 1.000 | 12 | 12 | 0 | 0 | 1.415 | — |
| G063 | 1.000 | 14 | 13 | 0 | 0 | 1.552 | — |
| G064 | 1.000 | 12 | 12 | 0 | 0 | 1.299 | — |
| G065 | 1.000 | 15 | 15 | 0 | 0 | 1.724 | — |
| G066 | 1.000 | 13 | 13 | 0 | 0 | 1.71 | — |
| G067 | 1.000 | 13 | 12 | 0 | 0 | 2.487 | — |
| G068 | 1.000 | 14 | 13 | 0 | 0 | 2.33 | — |
| G069 | 1.000 | 14 | 13 | 0 | 0 | 2.412 | — |
| G070 | 1.000 | 13 | 12 | 0 | 0 | 2.423 | — |
| G071 | 1.000 | 18 | 18 | 0 | 0 | 2.152 | — |
| G072 | 1.000 | 13 | 12 | 0 | 0 | 2.231 | — |
| G073 | 1.000 | 12 | 12 | 0 | 0 | 2.192 | — |
| G074 | 1.000 | 13 | 12 | 0 | 0 | 1.745 | — |
| G075 | 1.000 | 13 | 13 | 0 | 0 | 1.755 | — |
| G076 | 0.500 | 13 | 12 | 0 | 0 | 1.768 | 534 U.S. 184 |
| G077 | 1.000 | 13 | 12 | 0 | 0 | 1.795 | — |
| G078 | 1.000 | 13 | 12 | 0 | 0 | 1.749 | — |
| G079 | 1.000 | 14 | 13 | 0 | 0 | 2.126 | — |
| G080 | 1.000 | 12 | 11 | 0 | 0 | 1.939 | — |
| G081 | 0.500 | 10 | 10 | 0 | 0 | 1.613 | 42 U.S.C. § 12112 |
| G082 | 1.000 | 10 | 10 | 0 | 0 | 1.406 | — |
| G083 | 1.000 | 11 | 11 | 0 | 0 | 1.563 | — |
| G084 | 1.000 | 9 | 9 | 0 | 0 | 1.352 | — |
| G085 | 1.000 | 10 | 10 | 0 | 0 | 1.396 | — |
| G086 | 1.000 | 13 | 12 | 0 | 0 | 1.855 | — |
| G087 | 1.000 | 13 | 12 | 0 | 0 | 1.826 | — |
| G088 | 1.000 | 15 | 15 | 0 | 0 | 1.461 | — |
| G089 | 1.000 | 9 | 9 | 0 | 0 | 1.551 | — |
| G090 | 1.000 | 12 | 11 | 0 | 0 | 2.403 | — |
| G091 | 1.000 | 12 | 11 | 0 | 0 | 2.309 | — |
| G092 | 1.000 | 12 | 11 | 0 | 0 | 2.324 | — |
| G093 | 1.000 | 12 | 11 | 0 | 0 | 2.216 | — |
| G094 | 1.000 | 13 | 12 | 0 | 0 | 1.728 | — |
| G095 | 1.000 | 13 | 12 | 0 | 0 | 2.302 | — |
| G096 | 1.000 | 12 | 11 | 0 | 0 | 2.395 | — |
| G097 | 1.000 | 12 | 11 | 0 | 0 | 2.291 | — |
| G098 | 1.000 | 12 | 11 | 0 | 0 | 2.279 | — |
| G099 | 0.000 | 12 | 11 | 0 | 0 | 2.52 | 530 U.S. 133, 309 F.3d 893 |
| G100 | 0.000 | 12 | 11 | 0 | 0 | 2.364 | 29 U.S.C. § 631 |
