# STARE evaluation results

Generated 2026-10-17T15:32:33+00:00 with LLM provider `offline`, embedder `fastembed`, reranker `lexical`, on 100 gold questions (0 errors).

| Metric | Result | Target (Table 29) |
|---|---|---|
| Mata fixture: fabricated citations blocked | 6 of 6 non-exportable (3 blocked, 3 unresolved) | 6 of 6 |
| Unverified citations in exported memos | 0 | 0 |
| Citation accuracy (automated: exists + quote matches) | 1.000 | ≥ 0.94 |
| Hallucination rate (proposed memo citations failing the Firewall) | 0.000 | ≤ 0.02 |
| Retrieval recall@10 | 0.885 | ≥ 0.80 |
| Redaction coverage (auto engine) | 100.0% (27/27) | 100% |
| Redaction coverage (regex-only engine) | 96.3% (26/27) | — |
| Latency, approved plan to memo (p95) | 3.354 s | < 90 s |
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
| G001 | 1.000 | 16 | 16 | 0 | 0 | 3.848 | — |
| G002 | 1.000 | 16 | 16 | 0 | 0 | 2.936 | — |
| G003 | 1.000 | 16 | 16 | 0 | 0 | 2.628 | — |
| G004 | 1.000 | 16 | 16 | 0 | 0 | 2.807 | — |
| G005 | 1.000 | 16 | 16 | 0 | 0 | 2.431 | — |
| G006 | 1.000 | 16 | 16 | 0 | 0 | 2.769 | — |
| G007 | 1.000 | 16 | 16 | 0 | 0 | 2.541 | — |
| G008 | 0.000 | 16 | 16 | 0 | 0 | 2.555 | 532 U.S. 268 |
| G009 | 1.000 | 17 | 17 | 0 | 0 | 2.67 | — |
| G010 | 1.000 | 16 | 16 | 0 | 0 | 2.546 | — |
| G011 | 1.000 | 18 | 18 | 0 | 0 | 2.699 | — |
| G012 | 0.500 | 16 | 16 | 0 | 0 | 2.793 | 492 F.3d 551 |
| G013 | 1.000 | 16 | 16 | 0 | 0 | 2.814 | — |
| G014 | 1.000 | 16 | 16 | 0 | 0 | 2.563 | — |
| G015 | 1.000 | 16 | 16 | 0 | 0 | 2.717 | — |
| G016 | 0.500 | 16 | 16 | 0 | 0 | 2.645 | 281 F.3d 1054 |
| G017 | 1.000 | 16 | 16 | 0 | 0 | 2.698 | — |
| G018 | 0.000 | 16 | 16 | 0 | 0 | 2.573 | 532 U.S. 268 |
| G019 | 1.000 | 16 | 16 | 0 | 0 | 2.73 | — |
| G020 | 0.500 | 16 | 16 | 0 | 0 | 2.657 | 530 U.S. 133 |
| G021 | 1.000 | 13 | 12 | 0 | 0 | 3.127 | — |
| G022 | 0.500 | 13 | 13 | 0 | 0 | 2.954 | 450 U.S. 248 |
| G023 | 1.000 | 13 | 12 | 0 | 0 | 3.583 | — |
| G024 | 1.000 | 13 | 12 | 0 | 0 | 3.053 | — |
| G025 | 1.000 | 13 | 12 | 0 | 0 | 3.177 | — |
| G026 | 1.000 | 13 | 12 | 0 | 0 | 2.986 | — |
| G027 | 1.000 | 13 | 12 | 0 | 0 | 3.041 | — |
| G028 | 0.500 | 12 | 11 | 0 | 0 | 2.882 | 490 U.S. 228 |
| G029 | 1.000 | 13 | 13 | 0 | 0 | 3.35 | — |
| G030 | 1.000 | 13 | 13 | 0 | 0 | 2.888 | — |
| G031 | 1.000 | 13 | 12 | 0 | 0 | 3.06 | — |
| G032 | 1.000 | 13 | 13 | 0 | 0 | 3.352 | — |
| G033 | 1.000 | 13 | 12 | 0 | 0 | 2.867 | — |
| G034 | 1.000 | 13 | 12 | 0 | 0 | 2.819 | — |
| G035 | 1.000 | 13 | 12 | 0 | 0 | 3.111 | — |
| G036 | 0.500 | 12 | 11 | 0 | 0 | 2.955 | 492 F.3d 551 |
| G037 | 1.000 | 13 | 12 | 0 | 0 | 2.981 | — |
| G038 | 1.000 | 13 | 12 | 0 | 0 | 2.776 | — |
| G039 | 0.000 | 14 | 14 | 0 | 0 | 2.9 | 401 U.S. 424 |
| G040 | 1.000 | 13 | 12 | 0 | 0 | 3.007 | — |
| G041 | 0.000 | 13 | 12 | 0 | 0 | 3.216 | 411 U.S. 792, 349 F.3d 634 |
| G042 | 1.000 | 13 | 12 | 0 | 0 | 2.828 | — |
| G043 | 1.000 | 13 | 12 | 0 | 0 | 2.641 | — |
| G044 | 1.000 | 13 | 12 | 0 | 0 | 2.886 | — |
| G045 | 1.000 | 13 | 13 | 0 | 0 | 3.414 | — |
| G046 | 1.000 | 12 | 12 | 0 | 0 | 3.141 | — |
| G047 | 1.000 | 13 | 13 | 0 | 0 | 3.044 | — |
| G048 | 1.000 | 13 | 13 | 0 | 0 | 3.4 | — |
| G049 | 1.000 | 12 | 12 | 0 | 0 | 3.15 | — |
| G050 | 0.500 | 13 | 13 | 0 | 0 | 2.898 | 524 U.S. 775 |
| G051 | 1.000 | 12 | 12 | 0 | 0 | 2.978 | — |
| G052 | 1.000 | 12 | 12 | 0 | 0 | 3.031 | — |
| G053 | 0.500 | 12 | 12 | 0 | 0 | 3.01 | 524 U.S. 775 |
| G054 | 1.000 | 12 | 12 | 0 | 0 | 3.402 | — |
| G055 | 1.000 | 12 | 12 | 0 | 0 | 3.132 | — |
| G056 | 0.500 | 13 | 13 | 0 | 0 | 3.108 | 419 F.3d 885 |
| G057 | 0.500 | 12 | 12 | 0 | 0 | 3.323 | 360 F.3d 1103 |
| G058 | 1.000 | 12 | 12 | 0 | 0 | 3.073 | — |
| G059 | 1.000 | 13 | 13 | 0 | 0 | 2.963 | — |
| G060 | 1.000 | 12 | 12 | 0 | 0 | 3.134 | — |
| G061 | 1.000 | 16 | 15 | 0 | 0 | 1.94 | — |
| G062 | 1.000 | 13 | 13 | 0 | 0 | 1.852 | — |
| G063 | 1.000 | 16 | 15 | 0 | 0 | 2.01 | — |
| G064 | 1.000 | 13 | 13 | 0 | 0 | 1.737 | — |
| G065 | 1.000 | 14 | 14 | 0 | 0 | 1.989 | — |
| G066 | 1.000 | 14 | 14 | 0 | 0 | 1.979 | — |
| G067 | 1.000 | 14 | 13 | 0 | 0 | 2.997 | — |
| G068 | 1.000 | 14 | 13 | 0 | 0 | 2.871 | — |
| G069 | 1.000 | 13 | 12 | 0 | 0 | 2.863 | — |
| G070 | 1.000 | 13 | 12 | 0 | 0 | 3.026 | — |
| G071 | 1.000 | 17 | 17 | 0 | 0 | 2.531 | — |
| G072 | 1.000 | 13 | 12 | 0 | 0 | 2.984 | — |
| G073 | 1.000 | 13 | 12 | 0 | 0 | 2.41 | — |
| G074 | 1.000 | 12 | 12 | 0 | 0 | 2.141 | — |
| G075 | 1.000 | 13 | 13 | 0 | 0 | 2.184 | — |
| G076 | 0.500 | 13 | 13 | 0 | 0 | 2.235 | 534 U.S. 184 |
| G077 | 1.000 | 12 | 12 | 0 | 0 | 2.109 | — |
| G078 | 1.000 | 12 | 12 | 0 | 0 | 2.203 | — |
| G079 | 1.000 | 12 | 12 | 0 | 0 | 2.363 | — |
| G080 | 1.000 | 12 | 12 | 0 | 0 | 2.315 | — |
| G081 | 1.000 | 12 | 12 | 0 | 0 | 2.056 | — |
| G082 | 1.000 | 12 | 12 | 0 | 0 | 1.834 | — |
| G083 | 1.000 | 12 | 12 | 0 | 0 | 1.98 | — |
| G084 | 1.000 | 11 | 11 | 0 | 0 | 1.901 | — |
| G085 | 1.000 | 11 | 11 | 0 | 0 | 1.848 | — |
| G086 | 1.000 | 12 | 12 | 0 | 0 | 2.118 | — |
| G087 | 1.000 | 12 | 12 | 0 | 0 | 2.115 | — |
| G088 | 1.000 | 17 | 16 | 0 | 0 | 1.931 | — |
| G089 | 1.000 | 11 | 11 | 0 | 0 | 1.943 | — |
| G090 | 1.000 | 12 | 11 | 0 | 0 | 3.026 | — |
| G091 | 1.000 | 14 | 13 | 0 | 0 | 2.603 | — |
| G092 | 1.000 | 10 | 10 | 0 | 0 | 2.315 | — |
| G093 | 1.000 | 14 | 13 | 0 | 0 | 2.516 | — |
| G094 | 1.000 | 12 | 12 | 0 | 0 | 1.906 | — |
| G095 | 1.000 | 11 | 11 | 0 | 0 | 2.224 | — |
| G096 | 1.000 | 12 | 11 | 0 | 0 | 2.47 | — |
| G097 | 1.000 | 14 | 13 | 0 | 0 | 2.577 | — |
| G098 | 1.000 | 12 | 11 | 0 | 0 | 2.373 | — |
| G099 | 0.000 | 12 | 11 | 0 | 0 | 2.687 | 530 U.S. 133, 309 F.3d 893 |
| G100 | 0.000 | 10 | 10 | 0 | 0 | 2.3 | 29 U.S.C. § 631 |
