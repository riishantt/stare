# STARE evaluation results

Generated 2026-10-17T07:18:57+00:00 with LLM provider `offline`, embedder `lsa`, reranker `lexical`, on 100 gold questions (0 errors).

| Metric | Result | Target (Table 29) |
|---|---|---|
| Mata fixture: fabricated citations blocked | 6 of 6 non-exportable (3 blocked, 3 unresolved) | 6 of 6 |
| Unverified citations in exported memos | 0 | 0 |
| Citation accuracy (automated: exists + quote matches) | 1.000 | ≥ 0.94 |
| Hallucination rate (proposed memo citations failing the Firewall) | 0.000 | ≤ 0.02 |
| Retrieval recall@10 | 0.860 | ≥ 0.80 |
| Redaction coverage (auto engine) | 100.0% (27/27) | 100% |
| Redaction coverage (regex-only engine) | 96.3% (26/27) | — |
| Latency, approved plan to memo (p95) | 1.178 s | < 90 s |
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
| G001 | 1.000 | 17 | 17 | 0 | 0 | 2.37 | — |
| G002 | 1.000 | 17 | 17 | 0 | 0 | 0.999 | — |
| G003 | 1.000 | 17 | 17 | 0 | 0 | 0.862 | — |
| G004 | 1.000 | 17 | 17 | 0 | 0 | 0.88 | — |
| G005 | 1.000 | 17 | 17 | 0 | 0 | 0.823 | — |
| G006 | 1.000 | 17 | 17 | 0 | 0 | 0.941 | — |
| G007 | 1.000 | 17 | 17 | 0 | 0 | 0.876 | — |
| G008 | 0.000 | 18 | 18 | 0 | 0 | 0.853 | 532 U.S. 268 |
| G009 | 1.000 | 18 | 18 | 0 | 0 | 0.88 | — |
| G010 | 1.000 | 17 | 17 | 0 | 0 | 0.849 | — |
| G011 | 1.000 | 18 | 18 | 0 | 0 | 0.841 | — |
| G012 | 0.500 | 16 | 16 | 0 | 0 | 0.945 | 492 F.3d 551 |
| G013 | 1.000 | 17 | 17 | 0 | 0 | 0.873 | — |
| G014 | 1.000 | 17 | 17 | 0 | 0 | 0.874 | — |
| G015 | 1.000 | 17 | 17 | 0 | 0 | 0.958 | — |
| G016 | 0.000 | 17 | 17 | 0 | 0 | 0.867 | 570 U.S. 338, 281 F.3d 1054 |
| G017 | 1.000 | 17 | 17 | 0 | 0 | 0.9 | — |
| G018 | 0.000 | 17 | 17 | 0 | 0 | 0.87 | 532 U.S. 268 |
| G019 | 1.000 | 18 | 18 | 0 | 0 | 0.939 | — |
| G020 | 0.000 | 16 | 16 | 0 | 0 | 0.875 | 530 U.S. 133, 570 U.S. 338 |
| G021 | 1.000 | 12 | 11 | 0 | 0 | 1.193 | — |
| G022 | 0.500 | 12 | 12 | 0 | 0 | 0.944 | 450 U.S. 248 |
| G023 | 1.000 | 12 | 11 | 0 | 0 | 1.081 | — |
| G024 | 1.000 | 13 | 12 | 0 | 0 | 0.938 | — |
| G025 | 1.000 | 13 | 12 | 0 | 0 | 1.016 | — |
| G026 | 1.000 | 12 | 11 | 0 | 0 | 0.965 | — |
| G027 | 1.000 | 12 | 11 | 0 | 0 | 1.048 | — |
| G028 | 0.500 | 12 | 11 | 0 | 0 | 1.073 | 490 U.S. 228 |
| G029 | 0.000 | 12 | 12 | 0 | 0 | 0.995 | 490 U.S. 228 |
| G030 | 1.000 | 13 | 12 | 0 | 0 | 0.969 | — |
| G031 | 1.000 | 13 | 12 | 0 | 0 | 1.052 | — |
| G032 | 1.000 | 12 | 12 | 0 | 0 | 0.948 | — |
| G033 | 1.000 | 13 | 12 | 0 | 0 | 1.029 | — |
| G034 | 1.000 | 13 | 12 | 0 | 0 | 0.989 | — |
| G035 | 1.000 | 12 | 11 | 0 | 0 | 1.011 | — |
| G036 | 0.500 | 12 | 11 | 0 | 0 | 1.048 | 492 F.3d 551 |
| G037 | 1.000 | 12 | 11 | 0 | 0 | 1.01 | — |
| G038 | 1.000 | 12 | 11 | 0 | 0 | 0.992 | — |
| G039 | 0.000 | 12 | 12 | 0 | 0 | 0.954 | 401 U.S. 424 |
| G040 | 1.000 | 12 | 11 | 0 | 0 | 1.044 | — |
| G041 | 0.000 | 12 | 12 | 0 | 0 | 0.981 | 411 U.S. 792, 349 F.3d 634 |
| G042 | 1.000 | 13 | 12 | 0 | 0 | 0.963 | — |
| G043 | 1.000 | 12 | 12 | 0 | 0 | 0.9 | — |
| G044 | 1.000 | 13 | 12 | 0 | 0 | 0.995 | — |
| G045 | 1.000 | 14 | 14 | 0 | 0 | 1.25 | — |
| G046 | 1.000 | 14 | 14 | 0 | 0 | 1.131 | — |
| G047 | 1.000 | 13 | 13 | 0 | 0 | 1.104 | — |
| G048 | 1.000 | 14 | 14 | 0 | 0 | 1.237 | — |
| G049 | 1.000 | 13 | 13 | 0 | 0 | 1.077 | — |
| G050 | 1.000 | 13 | 13 | 0 | 0 | 1.007 | — |
| G051 | 1.000 | 13 | 13 | 0 | 0 | 1.102 | — |
| G052 | 1.000 | 12 | 12 | 0 | 0 | 1.031 | — |
| G053 | 0.000 | 13 | 13 | 0 | 0 | 1.061 | 524 U.S. 775, 532 U.S. 268 |
| G054 | 1.000 | 13 | 13 | 0 | 0 | 1.22 | — |
| G055 | 1.000 | 13 | 13 | 0 | 0 | 1.177 | — |
| G056 | 0.500 | 14 | 14 | 0 | 0 | 1.101 | 419 F.3d 885 |
| G057 | 0.500 | 13 | 13 | 0 | 0 | 1.008 | 510 U.S. 17 |
| G058 | 1.000 | 13 | 13 | 0 | 0 | 1.078 | — |
| G059 | 1.000 | 13 | 13 | 0 | 0 | 1.04 | — |
| G060 | 1.000 | 13 | 13 | 0 | 0 | 1.041 | — |
| G061 | 1.000 | 13 | 13 | 0 | 0 | 0.594 | — |
| G062 | 1.000 | 12 | 12 | 0 | 0 | 0.609 | — |
| G063 | 1.000 | 14 | 13 | 0 | 0 | 0.638 | — |
| G064 | 1.000 | 12 | 12 | 0 | 0 | 0.541 | — |
| G065 | 1.000 | 15 | 15 | 0 | 0 | 0.745 | — |
| G066 | 1.000 | 13 | 13 | 0 | 0 | 0.724 | — |
| G067 | 1.000 | 13 | 12 | 0 | 0 | 1.019 | — |
| G068 | 1.000 | 14 | 13 | 0 | 0 | 1.005 | — |
| G069 | 1.000 | 13 | 12 | 0 | 0 | 0.955 | — |
| G070 | 1.000 | 13 | 12 | 0 | 0 | 1.052 | — |
| G071 | 1.000 | 18 | 18 | 0 | 0 | 0.864 | — |
| G072 | 1.000 | 13 | 12 | 0 | 0 | 0.975 | — |
| G073 | 1.000 | 12 | 12 | 0 | 0 | 0.93 | — |
| G074 | 1.000 | 13 | 12 | 0 | 0 | 0.747 | — |
| G075 | 1.000 | 12 | 12 | 0 | 0 | 0.698 | — |
| G076 | 0.500 | 13 | 12 | 0 | 0 | 0.758 | 534 U.S. 184 |
| G077 | 1.000 | 12 | 11 | 0 | 0 | 0.703 | — |
| G078 | 1.000 | 13 | 12 | 0 | 0 | 0.746 | — |
| G079 | 1.000 | 13 | 12 | 0 | 0 | 0.839 | — |
| G080 | 1.000 | 13 | 12 | 0 | 0 | 0.876 | — |
| G081 | 0.500 | 10 | 10 | 0 | 0 | 0.669 | 42 U.S.C. § 12112 |
| G082 | 1.000 | 10 | 10 | 0 | 0 | 0.559 | — |
| G083 | 1.000 | 11 | 11 | 0 | 0 | 0.65 | — |
| G084 | 1.000 | 9 | 9 | 0 | 0 | 0.571 | — |
| G085 | 1.000 | 11 | 11 | 0 | 0 | 0.592 | — |
| G086 | 1.000 | 12 | 11 | 0 | 0 | 0.739 | — |
| G087 | 1.000 | 12 | 11 | 0 | 0 | 0.726 | — |
| G088 | 1.000 | 15 | 15 | 0 | 0 | 0.603 | — |
| G089 | 1.000 | 9 | 9 | 0 | 0 | 0.627 | — |
| G090 | 1.000 | 12 | 11 | 0 | 0 | 1.028 | — |
| G091 | 1.000 | 12 | 11 | 0 | 0 | 0.939 | — |
| G092 | 1.000 | 10 | 9 | 0 | 0 | 0.876 | — |
| G093 | 1.000 | 12 | 11 | 0 | 0 | 0.908 | — |
| G094 | 1.000 | 13 | 12 | 0 | 0 | 0.748 | — |
| G095 | 1.000 | 14 | 13 | 0 | 0 | 0.984 | — |
| G096 | 1.000 | 11 | 10 | 0 | 0 | 0.877 | — |
| G097 | 1.000 | 12 | 11 | 0 | 0 | 0.948 | — |
| G098 | 1.000 | 12 | 11 | 0 | 0 | 0.929 | — |
| G099 | 0.000 | 12 | 11 | 0 | 0 | 1.015 | 530 U.S. 133, 309 F.3d 893 |
| G100 | 0.000 | 12 | 11 | 0 | 0 | 0.944 | 29 U.S.C. § 631 |
