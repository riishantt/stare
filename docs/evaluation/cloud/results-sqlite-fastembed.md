# STARE evaluation results

Generated 2026-10-20T22:51:44+00:00 with LLM provider `offline`, embedder `fastembed`, reranker `lexical`, on 100 gold questions (0 errors).

| Metric | Result | Target (Table 29) |
|---|---|---|
| Mata fixture: fabricated citations blocked | 6 of 6 non-exportable (5 blocked, 1 unresolved) | 6 of 6 |
| Unverified citations in exported memos | 0 | 0 |
| Citation accuracy (automated): kept memo citations that exist and whose quotations match, verified or warning (1344 kept) | 1.000 | ≥ 0.94 |
| Citation accuracy (automated, strict): kept memo citations fully verified, no warning (1309 verified, 35 warning) | 0.974 | — |
| Hallucination rate: citations the drafter wrote that the memo Firewall blocked or left unresolved (0 of 798) | 0.000 | ≤ 0.02 |
| Retrieval recall@10 | 0.885 | ≥ 0.80 |
| Redaction coverage (auto engine) | 100.0% (27/27) | 100% |
| Redaction coverage (regex-only engine) | 96.3% (26/27) | — |
| Latency, approved plan to memo (p95) | 3.189 s | < 90 s |
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
| G001 | 1.000 | 16 | 16 | 0 | 0 | 3.53 | — |
| G002 | 1.000 | 16 | 16 | 0 | 0 | 2.665 | — |
| G003 | 1.000 | 16 | 16 | 0 | 0 | 2.38 | — |
| G004 | 1.000 | 16 | 16 | 0 | 0 | 2.829 | — |
| G005 | 1.000 | 16 | 16 | 0 | 0 | 2.308 | — |
| G006 | 1.000 | 16 | 16 | 0 | 0 | 2.621 | — |
| G007 | 1.000 | 16 | 16 | 0 | 0 | 2.17 | — |
| G008 | 0.000 | 16 | 16 | 0 | 0 | 2.232 | 532 U.S. 268 |
| G009 | 1.000 | 17 | 17 | 0 | 0 | 2.574 | — |
| G010 | 1.000 | 16 | 16 | 0 | 0 | 2.214 | — |
| G011 | 1.000 | 18 | 18 | 0 | 0 | 2.53 | — |
| G012 | 0.500 | 16 | 16 | 0 | 0 | 2.888 | 492 F.3d 551 |
| G013 | 1.000 | 16 | 16 | 0 | 0 | 2.292 | — |
| G014 | 1.000 | 16 | 16 | 0 | 0 | 2.711 | — |
| G015 | 1.000 | 16 | 16 | 0 | 0 | 2.453 | — |
| G016 | 0.500 | 16 | 16 | 0 | 0 | 2.351 | 281 F.3d 1054 |
| G017 | 1.000 | 16 | 16 | 0 | 0 | 2.421 | — |
| G018 | 0.000 | 16 | 16 | 0 | 0 | 2.642 | 532 U.S. 268 |
| G019 | 1.000 | 16 | 16 | 0 | 0 | 2.616 | — |
| G020 | 0.500 | 16 | 16 | 0 | 0 | 2.6 | 530 U.S. 133 |
| G021 | 1.000 | 13 | 12 | 0 | 0 | 2.755 | — |
| G022 | 0.500 | 13 | 13 | 0 | 0 | 2.482 | 450 U.S. 248 |
| G023 | 1.000 | 13 | 12 | 0 | 0 | 3.017 | — |
| G024 | 1.000 | 13 | 12 | 0 | 0 | 2.926 | — |
| G025 | 1.000 | 13 | 12 | 0 | 0 | 3.362 | — |
| G026 | 1.000 | 13 | 12 | 0 | 0 | 2.7 | — |
| G027 | 1.000 | 13 | 12 | 0 | 0 | 2.667 | — |
| G028 | 0.500 | 12 | 11 | 0 | 0 | 2.469 | 490 U.S. 228 |
| G029 | 1.000 | 13 | 13 | 0 | 0 | 2.863 | — |
| G030 | 1.000 | 13 | 13 | 0 | 0 | 2.493 | — |
| G031 | 1.000 | 13 | 12 | 0 | 0 | 2.786 | — |
| G032 | 1.000 | 13 | 13 | 0 | 0 | 2.546 | — |
| G033 | 1.000 | 13 | 12 | 0 | 0 | 3.051 | — |
| G034 | 1.000 | 13 | 12 | 0 | 0 | 3.154 | — |
| G035 | 1.000 | 13 | 12 | 0 | 0 | 2.622 | — |
| G036 | 0.500 | 12 | 11 | 0 | 0 | 2.679 | 492 F.3d 551 |
| G037 | 1.000 | 13 | 12 | 0 | 0 | 3.099 | — |
| G038 | 1.000 | 13 | 12 | 0 | 0 | 2.872 | — |
| G039 | 0.000 | 14 | 14 | 0 | 0 | 2.632 | 401 U.S. 424 |
| G040 | 1.000 | 13 | 12 | 0 | 0 | 2.641 | — |
| G041 | 0.000 | 13 | 12 | 0 | 0 | 2.913 | 411 U.S. 792, 349 F.3d 634 |
| G042 | 1.000 | 13 | 12 | 0 | 0 | 2.52 | — |
| G043 | 1.000 | 13 | 12 | 0 | 0 | 2.306 | — |
| G044 | 1.000 | 13 | 12 | 0 | 0 | 2.544 | — |
| G045 | 1.000 | 13 | 13 | 0 | 0 | 3.404 | — |
| G046 | 1.000 | 12 | 12 | 0 | 0 | 3.384 | — |
| G047 | 1.000 | 13 | 13 | 0 | 0 | 2.886 | — |
| G048 | 1.000 | 13 | 13 | 0 | 0 | 3.189 | — |
| G049 | 1.000 | 12 | 12 | 0 | 0 | 2.949 | — |
| G050 | 0.500 | 13 | 13 | 0 | 0 | 2.776 | 524 U.S. 775 |
| G051 | 1.000 | 12 | 12 | 0 | 0 | 2.961 | — |
| G052 | 1.000 | 12 | 12 | 0 | 0 | 2.719 | — |
| G053 | 0.500 | 12 | 12 | 0 | 0 | 2.754 | 524 U.S. 775 |
| G054 | 1.000 | 12 | 12 | 0 | 0 | 3.198 | — |
| G055 | 1.000 | 12 | 12 | 0 | 0 | 2.798 | — |
| G056 | 0.500 | 13 | 13 | 0 | 0 | 2.867 | 419 F.3d 885 |
| G057 | 0.500 | 12 | 12 | 0 | 0 | 2.997 | 360 F.3d 1103 |
| G058 | 1.000 | 12 | 12 | 0 | 0 | 2.867 | — |
| G059 | 1.000 | 13 | 13 | 0 | 0 | 3.008 | — |
| G060 | 1.000 | 12 | 12 | 0 | 0 | 2.638 | — |
| G061 | 1.000 | 16 | 15 | 0 | 0 | 1.626 | — |
| G062 | 1.000 | 13 | 13 | 0 | 0 | 1.532 | — |
| G063 | 1.000 | 16 | 15 | 0 | 0 | 1.988 | — |
| G064 | 1.000 | 13 | 13 | 0 | 0 | 1.765 | — |
| G065 | 1.000 | 14 | 14 | 0 | 0 | 1.778 | — |
| G066 | 1.000 | 14 | 14 | 0 | 0 | 1.745 | — |
| G067 | 1.000 | 14 | 13 | 0 | 0 | 2.919 | — |
| G068 | 1.000 | 14 | 13 | 0 | 0 | 2.748 | — |
| G069 | 1.000 | 13 | 12 | 0 | 0 | 2.86 | — |
| G070 | 1.000 | 13 | 12 | 0 | 0 | 3.108 | — |
| G071 | 1.000 | 17 | 17 | 0 | 0 | 2.786 | — |
| G072 | 1.000 | 13 | 12 | 0 | 0 | 2.952 | — |
| G073 | 1.000 | 13 | 12 | 0 | 0 | 2.113 | — |
| G074 | 1.000 | 12 | 12 | 0 | 0 | 2.34 | — |
| G075 | 1.000 | 13 | 13 | 0 | 0 | 1.841 | — |
| G076 | 0.500 | 13 | 13 | 0 | 0 | 1.983 | 534 U.S. 184 |
| G077 | 1.000 | 12 | 12 | 0 | 0 | 1.805 | — |
| G078 | 1.000 | 12 | 12 | 0 | 0 | 1.985 | — |
| G079 | 1.000 | 12 | 12 | 0 | 0 | 2.121 | — |
| G080 | 1.000 | 12 | 12 | 0 | 0 | 2.384 | — |
| G081 | 1.000 | 12 | 12 | 0 | 0 | 1.852 | — |
| G082 | 1.000 | 12 | 12 | 0 | 0 | 1.603 | — |
| G083 | 1.000 | 12 | 12 | 0 | 0 | 1.633 | — |
| G084 | 1.000 | 11 | 11 | 0 | 0 | 1.613 | — |
| G085 | 1.000 | 11 | 11 | 0 | 0 | 1.858 | — |
| G086 | 1.000 | 12 | 12 | 0 | 0 | 1.799 | — |
| G087 | 1.000 | 12 | 12 | 0 | 0 | 2.008 | — |
| G088 | 1.000 | 17 | 16 | 0 | 0 | 1.405 | — |
| G089 | 1.000 | 11 | 11 | 0 | 0 | 1.618 | — |
| G090 | 1.000 | 12 | 11 | 0 | 0 | 2.329 | — |
| G091 | 1.000 | 14 | 13 | 0 | 0 | 2.457 | — |
| G092 | 1.000 | 10 | 10 | 0 | 0 | 2.264 | — |
| G093 | 1.000 | 14 | 13 | 0 | 0 | 2.528 | — |
| G094 | 1.000 | 12 | 12 | 0 | 0 | 1.739 | — |
| G095 | 1.000 | 11 | 11 | 0 | 0 | 2.119 | — |
| G096 | 1.000 | 12 | 11 | 0 | 0 | 2.556 | — |
| G097 | 1.000 | 14 | 13 | 0 | 0 | 2.586 | — |
| G098 | 1.000 | 12 | 11 | 0 | 0 | 2.038 | — |
| G099 | 0.000 | 12 | 11 | 0 | 0 | 2.426 | 530 U.S. 133, 309 F.3d 893 |
| G100 | 0.000 | 10 | 10 | 0 | 0 | 1.959 | 29 U.S.C. § 631 |
