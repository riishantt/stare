# STARE evaluation results

Generated 2026-10-17T15:32:13+00:00 with LLM provider `offline`, embedder `fastembed`, reranker `lexical`, on 100 gold questions (0 errors).

| Metric | Result | Target (Table 29) |
|---|---|---|
| Mata fixture: fabricated citations blocked | 6 of 6 non-exportable (3 blocked, 3 unresolved) | 6 of 6 |
| Unverified citations in exported memos | 0 | 0 |
| Citation accuracy (automated: exists + quote matches) | 1.000 | ≥ 0.94 |
| Hallucination rate (proposed memo citations failing the Firewall) | 0.000 | ≤ 0.02 |
| Retrieval recall@10 | 0.885 | ≥ 0.80 |
| Redaction coverage (auto engine) | 100.0% (27/27) | 100% |
| Redaction coverage (regex-only engine) | 96.3% (26/27) | — |
| Latency, approved plan to memo (p95) | 3.088 s | < 90 s |
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
| G001 | 1.000 | 16 | 16 | 0 | 0 | 3.693 | — |
| G002 | 1.000 | 16 | 16 | 0 | 0 | 2.665 | — |
| G003 | 1.000 | 16 | 16 | 0 | 0 | 2.225 | — |
| G004 | 1.000 | 16 | 16 | 0 | 0 | 2.54 | — |
| G005 | 1.000 | 16 | 16 | 0 | 0 | 2.097 | — |
| G006 | 1.000 | 16 | 16 | 0 | 0 | 2.665 | — |
| G007 | 1.000 | 16 | 16 | 0 | 0 | 2.432 | — |
| G008 | 0.000 | 16 | 16 | 0 | 0 | 2.272 | 532 U.S. 268 |
| G009 | 1.000 | 17 | 17 | 0 | 0 | 2.834 | — |
| G010 | 1.000 | 16 | 16 | 0 | 0 | 2.264 | — |
| G011 | 1.000 | 18 | 18 | 0 | 0 | 2.44 | — |
| G012 | 0.500 | 16 | 16 | 0 | 0 | 2.52 | 492 F.3d 551 |
| G013 | 1.000 | 16 | 16 | 0 | 0 | 2.128 | — |
| G014 | 1.000 | 16 | 16 | 0 | 0 | 2.254 | — |
| G015 | 1.000 | 16 | 16 | 0 | 0 | 2.419 | — |
| G016 | 0.500 | 16 | 16 | 0 | 0 | 2.375 | 281 F.3d 1054 |
| G017 | 1.000 | 16 | 16 | 0 | 0 | 2.378 | — |
| G018 | 0.000 | 16 | 16 | 0 | 0 | 2.353 | 532 U.S. 268 |
| G019 | 1.000 | 16 | 16 | 0 | 0 | 2.673 | — |
| G020 | 0.500 | 16 | 16 | 0 | 0 | 2.442 | 530 U.S. 133 |
| G021 | 1.000 | 13 | 12 | 0 | 0 | 3.189 | — |
| G022 | 0.500 | 13 | 13 | 0 | 0 | 2.561 | 450 U.S. 248 |
| G023 | 1.000 | 13 | 12 | 0 | 0 | 2.964 | — |
| G024 | 1.000 | 13 | 12 | 0 | 0 | 2.897 | — |
| G025 | 1.000 | 13 | 12 | 0 | 0 | 2.92 | — |
| G026 | 1.000 | 13 | 12 | 0 | 0 | 2.74 | — |
| G027 | 1.000 | 13 | 12 | 0 | 0 | 2.738 | — |
| G028 | 0.500 | 12 | 11 | 0 | 0 | 2.422 | 490 U.S. 228 |
| G029 | 1.000 | 13 | 13 | 0 | 0 | 2.58 | — |
| G030 | 1.000 | 13 | 13 | 0 | 0 | 2.574 | — |
| G031 | 1.000 | 13 | 12 | 0 | 0 | 2.677 | — |
| G032 | 1.000 | 13 | 13 | 0 | 0 | 2.83 | — |
| G033 | 1.000 | 13 | 12 | 0 | 0 | 2.596 | — |
| G034 | 1.000 | 13 | 12 | 0 | 0 | 2.668 | — |
| G035 | 1.000 | 13 | 12 | 0 | 0 | 2.541 | — |
| G036 | 0.500 | 12 | 11 | 0 | 0 | 2.589 | 492 F.3d 551 |
| G037 | 1.000 | 13 | 12 | 0 | 0 | 2.912 | — |
| G038 | 1.000 | 13 | 12 | 0 | 0 | 2.849 | — |
| G039 | 0.000 | 14 | 14 | 0 | 0 | 2.946 | 401 U.S. 424 |
| G040 | 1.000 | 13 | 12 | 0 | 0 | 3.095 | — |
| G041 | 0.000 | 13 | 12 | 0 | 0 | 2.945 | 411 U.S. 792, 349 F.3d 634 |
| G042 | 1.000 | 13 | 12 | 0 | 0 | 2.62 | — |
| G043 | 1.000 | 13 | 12 | 0 | 0 | 2.391 | — |
| G044 | 1.000 | 13 | 12 | 0 | 0 | 2.432 | — |
| G045 | 1.000 | 13 | 13 | 0 | 0 | 3.019 | — |
| G046 | 1.000 | 12 | 12 | 0 | 0 | 2.997 | — |
| G047 | 1.000 | 13 | 13 | 0 | 0 | 2.735 | — |
| G048 | 1.000 | 13 | 13 | 0 | 0 | 3.088 | — |
| G049 | 1.000 | 12 | 12 | 0 | 0 | 3.0 | — |
| G050 | 0.500 | 13 | 13 | 0 | 0 | 2.634 | 524 U.S. 775 |
| G051 | 1.000 | 12 | 12 | 0 | 0 | 2.623 | — |
| G052 | 1.000 | 12 | 12 | 0 | 0 | 2.846 | — |
| G053 | 0.500 | 12 | 12 | 0 | 0 | 3.025 | 524 U.S. 775 |
| G054 | 1.000 | 12 | 12 | 0 | 0 | 3.592 | — |
| G055 | 1.000 | 12 | 12 | 0 | 0 | 2.726 | — |
| G056 | 0.500 | 13 | 13 | 0 | 0 | 3.084 | 419 F.3d 885 |
| G057 | 0.500 | 12 | 12 | 0 | 0 | 3.121 | 360 F.3d 1103 |
| G058 | 1.000 | 12 | 12 | 0 | 0 | 2.896 | — |
| G059 | 1.000 | 13 | 13 | 0 | 0 | 2.581 | — |
| G060 | 1.000 | 12 | 12 | 0 | 0 | 2.619 | — |
| G061 | 1.000 | 16 | 15 | 0 | 0 | 1.611 | — |
| G062 | 1.000 | 13 | 13 | 0 | 0 | 1.57 | — |
| G063 | 1.000 | 16 | 15 | 0 | 0 | 1.761 | — |
| G064 | 1.000 | 13 | 13 | 0 | 0 | 1.473 | — |
| G065 | 1.000 | 14 | 14 | 0 | 0 | 1.862 | — |
| G066 | 1.000 | 14 | 14 | 0 | 0 | 1.705 | — |
| G067 | 1.000 | 14 | 13 | 0 | 0 | 2.791 | — |
| G068 | 1.000 | 14 | 13 | 0 | 0 | 2.642 | — |
| G069 | 1.000 | 13 | 12 | 0 | 0 | 2.79 | — |
| G070 | 1.000 | 13 | 12 | 0 | 0 | 2.76 | — |
| G071 | 1.000 | 17 | 17 | 0 | 0 | 2.217 | — |
| G072 | 1.000 | 13 | 12 | 0 | 0 | 2.984 | — |
| G073 | 1.000 | 13 | 12 | 0 | 0 | 2.177 | — |
| G074 | 1.000 | 12 | 12 | 0 | 0 | 2.013 | — |
| G075 | 1.000 | 13 | 13 | 0 | 0 | 1.808 | — |
| G076 | 0.500 | 13 | 13 | 0 | 0 | 1.968 | 534 U.S. 184 |
| G077 | 1.000 | 12 | 12 | 0 | 0 | 1.808 | — |
| G078 | 1.000 | 12 | 12 | 0 | 0 | 1.923 | — |
| G079 | 1.000 | 12 | 12 | 0 | 0 | 2.139 | — |
| G080 | 1.000 | 12 | 12 | 0 | 0 | 2.029 | — |
| G081 | 1.000 | 12 | 12 | 0 | 0 | 1.823 | — |
| G082 | 1.000 | 12 | 12 | 0 | 0 | 1.756 | — |
| G083 | 1.000 | 12 | 12 | 0 | 0 | 1.853 | — |
| G084 | 1.000 | 11 | 11 | 0 | 0 | 1.622 | — |
| G085 | 1.000 | 11 | 11 | 0 | 0 | 1.722 | — |
| G086 | 1.000 | 12 | 12 | 0 | 0 | 1.967 | — |
| G087 | 1.000 | 12 | 12 | 0 | 0 | 1.892 | — |
| G088 | 1.000 | 17 | 16 | 0 | 0 | 1.484 | — |
| G089 | 1.000 | 11 | 11 | 0 | 0 | 1.833 | — |
| G090 | 1.000 | 12 | 11 | 0 | 0 | 2.446 | — |
| G091 | 1.000 | 14 | 13 | 0 | 0 | 2.487 | — |
| G092 | 1.000 | 10 | 10 | 0 | 0 | 2.136 | — |
| G093 | 1.000 | 14 | 13 | 0 | 0 | 2.22 | — |
| G094 | 1.000 | 12 | 12 | 0 | 0 | 1.693 | — |
| G095 | 1.000 | 11 | 11 | 0 | 0 | 2.098 | — |
| G096 | 1.000 | 12 | 11 | 0 | 0 | 2.157 | — |
| G097 | 1.000 | 14 | 13 | 0 | 0 | 2.21 | — |
| G098 | 1.000 | 12 | 11 | 0 | 0 | 2.028 | — |
| G099 | 0.000 | 12 | 11 | 0 | 0 | 2.352 | 530 U.S. 133, 309 F.3d 893 |
| G100 | 0.000 | 10 | 10 | 0 | 0 | 2.23 | 29 U.S.C. § 631 |
