# STARE evaluation results

Generated 2026-10-20T22:33:30+00:00 with LLM provider `offline`, embedder `lsa`, reranker `lexical`, on 100 gold questions (0 errors).

| Metric | Result | Target (Table 29) |
|---|---|---|
| Mata fixture: fabricated citations blocked | 6 of 6 non-exportable (6 blocked, 0 unresolved) | 6 of 6 |
| Unverified citations in exported memos | 0 | 0 |
| Citation accuracy (automated): kept memo citations that exist and whose quotations match, verified or warning (1344 kept) | 1.000 | ≥ 0.94 |
| Citation accuracy (automated, strict): kept memo citations fully verified, no warning (1301 verified, 43 warning) | 0.968 | — |
| Hallucination rate: citations the drafter wrote that the memo Firewall blocked or left unresolved (0 of 785) | 0.000 | ≤ 0.02 |
| Retrieval recall@10 | 0.860 | ≥ 0.80 |
| Redaction coverage (auto engine) | 100.0% (27/27) | 100% |
| Redaction coverage (regex-only engine) | 96.3% (26/27) | — |
| Latency, approved plan to memo (p95) | 1.231 s | < 90 s |
| Citation accuracy, reviewed: exists **and supports the statement** (74 citations from the offline run, [support_review.md](support_review.md)) | 0.986 | ≥ 0.94 |
| Hallucination rate, reviewed: citations that do not support their statement | 0.014 | ≤ 0.02 |
| Baseline comparison: citation accuracy, general-purpose LLM without retrieval (`opencode/beam-free (free general-purpose LLM, no retrieval)`, 100 questions, 564 citations) | 0.965 (STARE 1.000) | STARE higher |
| Baseline accuracy over citations the Firewall could check (10 unresolved excluded) | 0.982 | — |
| Baseline citations blocked as nonexistent or misquoted | 10 of 564 | — |

Notes:
- Citation counts are per occurrence. The automated accuracy is measured over the citations left in the final memos, after the Firewall removed failing ones, so it counts warnings (e.g. a near-match quotation or good-law status not checked) as accurate; the strict row counts only fully verified citations. The hallucination rate counts the citations the drafter (the LLM, or the offline extractive drafter) wrote in the issue, rule, application and conclusion, before the memo Firewall pass; the question presented and the adverse-authority list are not drafted (they come from the gold question and the Firewall-checked adverse authorities). `hallucination_rate` in results.json keeps the earlier definition for comparison with older reports.
- The automated citation accuracy checks that each citation exists in court records and every quotation matches the opinion; the reviewed rows add whether each authority supports its statement (the Table 29 manual check of a 20-question sample, every verdict listed in support_review.md; validation with practising lawyers is future scope, Section 7.4).
- In offline mode the memo is drafted extractively from verified passages, so the hallucination rate measures the pipeline's guarantees. The baseline rows score a free general-purpose LLM answering the same questions without retrieval (`stare eval baseline --answers`); citations the free CourtListener API could not check (rate limit) are counted as unresolved.

## Per-question results

| Question | recall@10 | memo citations | verified | removed | export violations | latency (s) | missed expected |
|---|---|---|---|---|---|---|---|
| G001 | 1.000 | 17 | 17 | 0 | 0 | 2.45 | — |
| G002 | 1.000 | 17 | 17 | 0 | 0 | 1.05 | — |
| G003 | 1.000 | 17 | 17 | 0 | 0 | 0.902 | — |
| G004 | 1.000 | 17 | 17 | 0 | 0 | 0.93 | — |
| G005 | 1.000 | 17 | 17 | 0 | 0 | 0.889 | — |
| G006 | 1.000 | 17 | 17 | 0 | 0 | 1.003 | — |
| G007 | 1.000 | 17 | 17 | 0 | 0 | 0.941 | — |
| G008 | 0.000 | 18 | 18 | 0 | 0 | 0.895 | 532 U.S. 268 |
| G009 | 1.000 | 18 | 18 | 0 | 0 | 0.921 | — |
| G010 | 1.000 | 17 | 17 | 0 | 0 | 0.91 | — |
| G011 | 1.000 | 18 | 18 | 0 | 0 | 0.893 | — |
| G012 | 0.500 | 16 | 16 | 0 | 0 | 1.002 | 492 F.3d 551 |
| G013 | 1.000 | 17 | 17 | 0 | 0 | 0.957 | — |
| G014 | 1.000 | 17 | 17 | 0 | 0 | 0.93 | — |
| G015 | 1.000 | 17 | 17 | 0 | 0 | 1.024 | — |
| G016 | 0.000 | 17 | 17 | 0 | 0 | 0.926 | 570 U.S. 338, 281 F.3d 1054 |
| G017 | 1.000 | 17 | 17 | 0 | 0 | 0.959 | — |
| G018 | 0.000 | 17 | 17 | 0 | 0 | 0.918 | 532 U.S. 268 |
| G019 | 1.000 | 18 | 18 | 0 | 0 | 1.004 | — |
| G020 | 0.000 | 16 | 16 | 0 | 0 | 0.937 | 530 U.S. 133, 570 U.S. 338 |
| G021 | 1.000 | 12 | 11 | 0 | 0 | 1.29 | — |
| G022 | 0.500 | 12 | 12 | 0 | 0 | 1.007 | 450 U.S. 248 |
| G023 | 1.000 | 12 | 11 | 0 | 0 | 1.149 | — |
| G024 | 1.000 | 13 | 12 | 0 | 0 | 0.993 | — |
| G025 | 1.000 | 13 | 12 | 0 | 0 | 1.075 | — |
| G026 | 1.000 | 12 | 11 | 0 | 0 | 1.035 | — |
| G027 | 1.000 | 12 | 11 | 0 | 0 | 1.113 | — |
| G028 | 0.500 | 12 | 11 | 0 | 0 | 1.177 | 490 U.S. 228 |
| G029 | 0.000 | 12 | 12 | 0 | 0 | 1.07 | 490 U.S. 228 |
| G030 | 1.000 | 13 | 12 | 0 | 0 | 1.045 | — |
| G031 | 1.000 | 13 | 12 | 0 | 0 | 1.138 | — |
| G032 | 1.000 | 12 | 12 | 0 | 0 | 1.025 | — |
| G033 | 1.000 | 13 | 12 | 0 | 0 | 1.11 | — |
| G034 | 1.000 | 13 | 12 | 0 | 0 | 1.061 | — |
| G035 | 1.000 | 12 | 11 | 0 | 0 | 1.081 | — |
| G036 | 0.500 | 12 | 11 | 0 | 0 | 1.128 | 492 F.3d 551 |
| G037 | 1.000 | 12 | 11 | 0 | 0 | 1.077 | — |
| G038 | 1.000 | 12 | 11 | 0 | 0 | 1.056 | — |
| G039 | 0.000 | 12 | 12 | 0 | 0 | 1.017 | 401 U.S. 424 |
| G040 | 1.000 | 12 | 11 | 0 | 0 | 1.152 | — |
| G041 | 0.000 | 12 | 12 | 0 | 0 | 1.044 | 411 U.S. 792, 349 F.3d 634 |
| G042 | 1.000 | 13 | 12 | 0 | 0 | 1.042 | — |
| G043 | 1.000 | 12 | 12 | 0 | 0 | 0.968 | — |
| G044 | 1.000 | 13 | 12 | 0 | 0 | 1.062 | — |
| G045 | 1.000 | 14 | 14 | 0 | 0 | 1.357 | — |
| G046 | 1.000 | 14 | 14 | 0 | 0 | 1.208 | — |
| G047 | 1.000 | 13 | 13 | 0 | 0 | 1.159 | — |
| G048 | 1.000 | 14 | 14 | 0 | 0 | 1.317 | — |
| G049 | 1.000 | 13 | 13 | 0 | 0 | 1.184 | — |
| G050 | 1.000 | 13 | 13 | 0 | 0 | 1.083 | — |
| G051 | 1.000 | 13 | 13 | 0 | 0 | 1.17 | — |
| G052 | 1.000 | 12 | 12 | 0 | 0 | 1.105 | — |
| G053 | 0.000 | 13 | 13 | 0 | 0 | 1.152 | 524 U.S. 775, 532 U.S. 268 |
| G054 | 1.000 | 13 | 13 | 0 | 0 | 1.302 | — |
| G055 | 1.000 | 13 | 13 | 0 | 0 | 1.228 | — |
| G056 | 0.500 | 14 | 14 | 0 | 0 | 1.168 | 419 F.3d 885 |
| G057 | 0.500 | 13 | 13 | 0 | 0 | 1.071 | 510 U.S. 17 |
| G058 | 1.000 | 13 | 13 | 0 | 0 | 1.15 | — |
| G059 | 1.000 | 13 | 13 | 0 | 0 | 1.117 | — |
| G060 | 1.000 | 13 | 13 | 0 | 0 | 1.119 | — |
| G061 | 1.000 | 13 | 13 | 0 | 0 | 0.641 | — |
| G062 | 1.000 | 12 | 12 | 0 | 0 | 0.652 | — |
| G063 | 1.000 | 14 | 13 | 0 | 0 | 0.691 | — |
| G064 | 1.000 | 12 | 12 | 0 | 0 | 0.595 | — |
| G065 | 1.000 | 15 | 15 | 0 | 0 | 0.799 | — |
| G066 | 1.000 | 13 | 13 | 0 | 0 | 0.77 | — |
| G067 | 1.000 | 13 | 12 | 0 | 0 | 1.074 | — |
| G068 | 1.000 | 14 | 13 | 0 | 0 | 1.071 | — |
| G069 | 1.000 | 13 | 12 | 0 | 0 | 1.021 | — |
| G070 | 1.000 | 13 | 12 | 0 | 0 | 1.117 | — |
| G071 | 1.000 | 18 | 18 | 0 | 0 | 0.908 | — |
| G072 | 1.000 | 13 | 12 | 0 | 0 | 1.036 | — |
| G073 | 1.000 | 12 | 12 | 0 | 0 | 0.996 | — |
| G074 | 1.000 | 13 | 12 | 0 | 0 | 0.804 | — |
| G075 | 1.000 | 12 | 12 | 0 | 0 | 0.738 | — |
| G076 | 0.500 | 13 | 12 | 0 | 0 | 0.8 | 534 U.S. 184 |
| G077 | 1.000 | 12 | 11 | 0 | 0 | 0.746 | — |
| G078 | 1.000 | 13 | 12 | 0 | 0 | 0.791 | — |
| G079 | 1.000 | 13 | 12 | 0 | 0 | 0.888 | — |
| G080 | 1.000 | 13 | 12 | 0 | 0 | 0.922 | — |
| G081 | 0.500 | 10 | 10 | 0 | 0 | 0.707 | 42 U.S.C. § 12112 |
| G082 | 1.000 | 10 | 10 | 0 | 0 | 0.6 | — |
| G083 | 1.000 | 11 | 11 | 0 | 0 | 0.686 | — |
| G084 | 1.000 | 9 | 9 | 0 | 0 | 0.591 | — |
| G085 | 1.000 | 11 | 11 | 0 | 0 | 0.618 | — |
| G086 | 1.000 | 12 | 11 | 0 | 0 | 0.823 | — |
| G087 | 1.000 | 12 | 11 | 0 | 0 | 0.77 | — |
| G088 | 1.000 | 15 | 15 | 0 | 0 | 0.639 | — |
| G089 | 1.000 | 9 | 9 | 0 | 0 | 0.652 | — |
| G090 | 1.000 | 12 | 11 | 0 | 0 | 1.084 | — |
| G091 | 1.000 | 12 | 11 | 0 | 0 | 0.992 | — |
| G092 | 1.000 | 10 | 9 | 0 | 0 | 0.934 | — |
| G093 | 1.000 | 12 | 11 | 0 | 0 | 0.96 | — |
| G094 | 1.000 | 13 | 12 | 0 | 0 | 0.78 | — |
| G095 | 1.000 | 14 | 13 | 0 | 0 | 1.023 | — |
| G096 | 1.000 | 11 | 10 | 0 | 0 | 0.92 | — |
| G097 | 1.000 | 12 | 11 | 0 | 0 | 1.001 | — |
| G098 | 1.000 | 12 | 11 | 0 | 0 | 0.981 | — |
| G099 | 0.000 | 12 | 11 | 0 | 0 | 1.063 | 530 U.S. 133, 309 F.3d 893 |
| G100 | 0.000 | 12 | 11 | 0 | 0 | 0.99 | 29 U.S.C. § 631 |
