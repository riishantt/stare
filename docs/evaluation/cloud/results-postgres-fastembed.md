# STARE evaluation results

Generated 2026-10-20T22:51:27+00:00 with LLM provider `offline`, embedder `fastembed`, reranker `lexical`, on 100 gold questions (0 errors).

| Metric | Result | Target (Table 29) |
|---|---|---|
| Mata fixture: fabricated citations blocked | 6 of 6 non-exportable (6 blocked, 0 unresolved) | 6 of 6 |
| Unverified citations in exported memos | 0 | 0 |
| Citation accuracy (automated): kept memo citations that exist and whose quotations match, verified or warning (1344 kept) | 1.000 | ≥ 0.94 |
| Citation accuracy (automated, strict): kept memo citations fully verified, no warning (1309 verified, 35 warning) | 0.974 | — |
| Hallucination rate: citations the drafter wrote that the memo Firewall blocked or left unresolved (0 of 798) | 0.000 | ≤ 0.02 |
| Retrieval recall@10 | 0.885 | ≥ 0.80 |
| Redaction coverage (auto engine) | 100.0% (27/27) | 100% |
| Redaction coverage (regex-only engine) | 96.3% (26/27) | — |
| Latency, approved plan to memo (p95) | 3.194 s | < 90 s |
| Citation accuracy, reviewed: exists **and supports the statement** (74 citations from the offline run, [support_review.md](support_review.md)) | 0.986 | ≥ 0.94 |
| Hallucination rate, reviewed: citations that do not support their statement | 0.014 | ≤ 0.02 |
| Baseline comparison: citation accuracy, general-purpose LLM without retrieval (`opencode/beam-free (free general-purpose LLM, no retrieval)`, 100 questions, 563 citations) | 0.979 (STARE 1.000) | STARE higher |
| Baseline accuracy over citations the Firewall could check (5 unresolved excluded) | 0.987 | — |
| Baseline citations blocked as nonexistent or misquoted | 6 of 563 | — |

Notes:
- Citation counts are per occurrence. The automated accuracy is measured over the citations left in the final memos, after the Firewall removed failing ones, so it counts warnings (e.g. a near-match quotation or good-law status not checked) as accurate; the strict row counts only fully verified citations. The hallucination rate counts the citations the drafter (the LLM, or the offline extractive drafter) wrote in the issue, rule, application and conclusion, before the memo Firewall pass; the question presented and the adverse-authority list are not drafted (they come from the gold question and the Firewall-checked adverse authorities). `hallucination_rate` in results.json keeps the earlier definition for comparison with older reports.
- The automated citation accuracy checks that each citation exists in court records and every quotation matches the opinion; the reviewed rows add whether each authority supports its statement (the Table 29 manual check of a 20-question sample, every verdict listed in support_review.md; validation with practising lawyers is future scope, Section 7.4).
- In offline mode the memo is drafted extractively from verified passages, so the hallucination rate measures the pipeline's guarantees. The baseline rows score a free general-purpose LLM answering the same questions without retrieval (`stare eval baseline --answers`); citations the free CourtListener API could not check (rate limit) are counted as unresolved.

## Per-question results

| Question | recall@10 | memo citations | verified | removed | export violations | latency (s) | missed expected |
|---|---|---|---|---|---|---|---|
| G001 | 1.000 | 16 | 16 | 0 | 0 | 3.763 | — |
| G002 | 1.000 | 16 | 16 | 0 | 0 | 2.949 | — |
| G003 | 1.000 | 16 | 16 | 0 | 0 | 2.52 | — |
| G004 | 1.000 | 16 | 16 | 0 | 0 | 2.8 | — |
| G005 | 1.000 | 16 | 16 | 0 | 0 | 2.39 | — |
| G006 | 1.000 | 16 | 16 | 0 | 0 | 2.785 | — |
| G007 | 1.000 | 16 | 16 | 0 | 0 | 2.564 | — |
| G008 | 0.000 | 16 | 16 | 0 | 0 | 2.537 | 532 U.S. 268 |
| G009 | 1.000 | 17 | 17 | 0 | 0 | 2.711 | — |
| G010 | 1.000 | 16 | 16 | 0 | 0 | 2.555 | — |
| G011 | 1.000 | 18 | 18 | 0 | 0 | 2.63 | — |
| G012 | 0.500 | 16 | 16 | 0 | 0 | 2.778 | 492 F.3d 551 |
| G013 | 1.000 | 16 | 16 | 0 | 0 | 2.503 | — |
| G014 | 1.000 | 16 | 16 | 0 | 0 | 2.494 | — |
| G015 | 1.000 | 16 | 16 | 0 | 0 | 2.698 | — |
| G016 | 0.500 | 16 | 16 | 0 | 0 | 2.616 | 281 F.3d 1054 |
| G017 | 1.000 | 16 | 16 | 0 | 0 | 2.63 | — |
| G018 | 0.000 | 16 | 16 | 0 | 0 | 2.595 | 532 U.S. 268 |
| G019 | 1.000 | 16 | 16 | 0 | 0 | 2.731 | — |
| G020 | 0.500 | 16 | 16 | 0 | 0 | 2.631 | 530 U.S. 133 |
| G021 | 1.000 | 13 | 12 | 0 | 0 | 3.087 | — |
| G022 | 0.500 | 13 | 13 | 0 | 0 | 2.924 | 450 U.S. 248 |
| G023 | 1.000 | 13 | 12 | 0 | 0 | 3.106 | — |
| G024 | 1.000 | 13 | 12 | 0 | 0 | 3.021 | — |
| G025 | 1.000 | 13 | 12 | 0 | 0 | 3.183 | — |
| G026 | 1.000 | 13 | 12 | 0 | 0 | 2.986 | — |
| G027 | 1.000 | 13 | 12 | 0 | 0 | 3.026 | — |
| G028 | 0.500 | 12 | 11 | 0 | 0 | 2.828 | 490 U.S. 228 |
| G029 | 1.000 | 13 | 13 | 0 | 0 | 2.985 | — |
| G030 | 1.000 | 13 | 13 | 0 | 0 | 2.885 | — |
| G031 | 1.000 | 13 | 12 | 0 | 0 | 2.987 | — |
| G032 | 1.000 | 13 | 13 | 0 | 0 | 2.872 | — |
| G033 | 1.000 | 13 | 12 | 0 | 0 | 2.899 | — |
| G034 | 1.000 | 13 | 12 | 0 | 0 | 2.818 | — |
| G035 | 1.000 | 13 | 12 | 0 | 0 | 2.965 | — |
| G036 | 0.500 | 12 | 11 | 0 | 0 | 2.995 | 492 F.3d 551 |
| G037 | 1.000 | 13 | 12 | 0 | 0 | 2.956 | — |
| G038 | 1.000 | 13 | 12 | 0 | 0 | 2.822 | — |
| G039 | 0.000 | 14 | 14 | 0 | 0 | 2.936 | 401 U.S. 424 |
| G040 | 1.000 | 13 | 12 | 0 | 0 | 3.045 | — |
| G041 | 0.000 | 13 | 12 | 0 | 0 | 3.024 | 411 U.S. 792, 349 F.3d 634 |
| G042 | 1.000 | 13 | 12 | 0 | 0 | 2.835 | — |
| G043 | 1.000 | 13 | 12 | 0 | 0 | 2.626 | — |
| G044 | 1.000 | 13 | 12 | 0 | 0 | 2.891 | — |
| G045 | 1.000 | 13 | 13 | 0 | 0 | 3.407 | — |
| G046 | 1.000 | 12 | 12 | 0 | 0 | 3.169 | — |
| G047 | 1.000 | 13 | 13 | 0 | 0 | 3.092 | — |
| G048 | 1.000 | 13 | 13 | 0 | 0 | 3.402 | — |
| G049 | 1.000 | 12 | 12 | 0 | 0 | 3.155 | — |
| G050 | 0.500 | 13 | 13 | 0 | 0 | 2.964 | 524 U.S. 775 |
| G051 | 1.000 | 12 | 12 | 0 | 0 | 3.041 | — |
| G052 | 1.000 | 12 | 12 | 0 | 0 | 3.081 | — |
| G053 | 0.500 | 12 | 12 | 0 | 0 | 3.035 | 524 U.S. 775 |
| G054 | 1.000 | 12 | 12 | 0 | 0 | 3.437 | — |
| G055 | 1.000 | 12 | 12 | 0 | 0 | 3.124 | — |
| G056 | 0.500 | 13 | 13 | 0 | 0 | 3.172 | 419 F.3d 885 |
| G057 | 0.500 | 12 | 12 | 0 | 0 | 3.404 | 360 F.3d 1103 |
| G058 | 1.000 | 12 | 12 | 0 | 0 | 3.136 | — |
| G059 | 1.000 | 13 | 13 | 0 | 0 | 3.007 | — |
| G060 | 1.000 | 12 | 12 | 0 | 0 | 3.009 | — |
| G061 | 1.000 | 16 | 15 | 0 | 0 | 2.053 | — |
| G062 | 1.000 | 13 | 13 | 0 | 0 | 1.87 | — |
| G063 | 1.000 | 16 | 15 | 0 | 0 | 2.082 | — |
| G064 | 1.000 | 13 | 13 | 0 | 0 | 1.751 | — |
| G065 | 1.000 | 14 | 14 | 0 | 0 | 2.038 | — |
| G066 | 1.000 | 14 | 14 | 0 | 0 | 2.015 | — |
| G067 | 1.000 | 14 | 13 | 0 | 0 | 3.102 | — |
| G068 | 1.000 | 14 | 13 | 0 | 0 | 2.925 | — |
| G069 | 1.000 | 13 | 12 | 0 | 0 | 2.961 | — |
| G070 | 1.000 | 13 | 12 | 0 | 0 | 3.039 | — |
| G071 | 1.000 | 17 | 17 | 0 | 0 | 2.588 | — |
| G072 | 1.000 | 13 | 12 | 0 | 0 | 2.999 | — |
| G073 | 1.000 | 13 | 12 | 0 | 0 | 2.428 | — |
| G074 | 1.000 | 12 | 12 | 0 | 0 | 2.19 | — |
| G075 | 1.000 | 13 | 13 | 0 | 0 | 2.185 | — |
| G076 | 0.500 | 13 | 13 | 0 | 0 | 2.267 | 534 U.S. 184 |
| G077 | 1.000 | 12 | 12 | 0 | 0 | 2.169 | — |
| G078 | 1.000 | 12 | 12 | 0 | 0 | 2.205 | — |
| G079 | 1.000 | 12 | 12 | 0 | 0 | 2.369 | — |
| G080 | 1.000 | 12 | 12 | 0 | 0 | 2.349 | — |
| G081 | 1.000 | 12 | 12 | 0 | 0 | 2.078 | — |
| G082 | 1.000 | 12 | 12 | 0 | 0 | 1.819 | — |
| G083 | 1.000 | 12 | 12 | 0 | 0 | 1.992 | — |
| G084 | 1.000 | 11 | 11 | 0 | 0 | 1.888 | — |
| G085 | 1.000 | 11 | 11 | 0 | 0 | 1.876 | — |
| G086 | 1.000 | 12 | 12 | 0 | 0 | 2.19 | — |
| G087 | 1.000 | 12 | 12 | 0 | 0 | 2.226 | — |
| G088 | 1.000 | 17 | 16 | 0 | 0 | 1.734 | — |
| G089 | 1.000 | 11 | 11 | 0 | 0 | 2.002 | — |
| G090 | 1.000 | 12 | 11 | 0 | 0 | 2.724 | — |
| G091 | 1.000 | 14 | 13 | 0 | 0 | 2.643 | — |
| G092 | 1.000 | 10 | 10 | 0 | 0 | 2.355 | — |
| G093 | 1.000 | 14 | 13 | 0 | 0 | 2.608 | — |
| G094 | 1.000 | 12 | 12 | 0 | 0 | 1.988 | — |
| G095 | 1.000 | 11 | 11 | 0 | 0 | 2.296 | — |
| G096 | 1.000 | 12 | 11 | 0 | 0 | 2.528 | — |
| G097 | 1.000 | 14 | 13 | 0 | 0 | 2.637 | — |
| G098 | 1.000 | 12 | 11 | 0 | 0 | 2.432 | — |
| G099 | 0.000 | 12 | 11 | 0 | 0 | 2.754 | 530 U.S. 133, 309 F.3d 893 |
| G100 | 0.000 | 10 | 10 | 0 | 0 | 2.347 | 29 U.S.C. § 631 |
