# STARE evaluation results

Generated 2026-10-20T22:36:56+00:00 with LLM provider `offline`, embedder `lsa`, reranker `lexical`, on 100 gold questions (0 errors).

| Metric | Result | Target (Table 29) |
|---|---|---|
| Mata fixture: fabricated citations blocked | 6 of 6 non-exportable (6 blocked, 0 unresolved) | 6 of 6 |
| Unverified citations in exported memos | 0 | 0 |
| Citation accuracy (automated): kept memo citations that exist and whose quotations match, verified or warning (1344 kept) | 1.000 | ≥ 0.94 |
| Citation accuracy (automated, strict): kept memo citations fully verified, no warning (1301 verified, 43 warning) | 0.968 | — |
| Hallucination rate: citations the drafter wrote that the memo Firewall blocked or left unresolved (0 of 777) | 0.000 | ≤ 0.02 |
| Retrieval recall@10 | 0.865 | ≥ 0.80 |
| Redaction coverage (auto engine) | 100.0% (27/27) | 100% |
| Redaction coverage (regex-only engine) | 96.3% (26/27) | — |
| Latency, approved plan to memo (p95) | 2.576 s | < 90 s |
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
| G001 | 1.000 | 16 | 16 | 0 | 0 | 3.835 | — |
| G002 | 1.000 | 16 | 16 | 0 | 0 | 2.315 | — |
| G003 | 1.000 | 16 | 16 | 0 | 0 | 2.019 | — |
| G004 | 1.000 | 17 | 17 | 0 | 0 | 2.158 | — |
| G005 | 1.000 | 16 | 16 | 0 | 0 | 1.954 | — |
| G006 | 1.000 | 16 | 16 | 0 | 0 | 2.092 | — |
| G007 | 1.000 | 16 | 16 | 0 | 0 | 1.97 | — |
| G008 | 0.000 | 17 | 17 | 0 | 0 | 2.051 | 532 U.S. 268 |
| G009 | 1.000 | 18 | 18 | 0 | 0 | 2.057 | — |
| G010 | 1.000 | 16 | 16 | 0 | 0 | 1.947 | — |
| G011 | 1.000 | 18 | 18 | 0 | 0 | 2.034 | — |
| G012 | 0.500 | 16 | 16 | 0 | 0 | 2.198 | 492 F.3d 551 |
| G013 | 1.000 | 16 | 16 | 0 | 0 | 1.964 | — |
| G014 | 1.000 | 16 | 16 | 0 | 0 | 1.981 | — |
| G015 | 1.000 | 16 | 16 | 0 | 0 | 2.151 | — |
| G016 | 0.500 | 16 | 16 | 0 | 0 | 2.078 | 281 F.3d 1054 |
| G017 | 1.000 | 17 | 17 | 0 | 0 | 2.132 | — |
| G018 | 0.000 | 16 | 16 | 0 | 0 | 2.007 | 532 U.S. 268 |
| G019 | 1.000 | 18 | 18 | 0 | 0 | 2.29 | — |
| G020 | 0.500 | 16 | 16 | 0 | 0 | 2.011 | 530 U.S. 133 |
| G021 | 0.000 | 12 | 11 | 0 | 0 | 2.279 | 411 U.S. 792 |
| G022 | 0.500 | 13 | 13 | 0 | 0 | 2.185 | 450 U.S. 248 |
| G023 | 1.000 | 12 | 11 | 0 | 0 | 2.564 | — |
| G024 | 1.000 | 12 | 11 | 0 | 0 | 2.319 | — |
| G025 | 1.000 | 12 | 11 | 0 | 0 | 2.282 | — |
| G026 | 1.000 | 13 | 12 | 0 | 0 | 2.14 | — |
| G027 | 1.000 | 14 | 13 | 0 | 0 | 2.363 | — |
| G028 | 0.500 | 12 | 11 | 0 | 0 | 2.35 | 490 U.S. 228 |
| G029 | 1.000 | 14 | 14 | 0 | 0 | 2.198 | — |
| G030 | 1.000 | 13 | 12 | 0 | 0 | 2.113 | — |
| G031 | 1.000 | 14 | 13 | 0 | 0 | 2.468 | — |
| G032 | 1.000 | 12 | 12 | 0 | 0 | 2.3 | — |
| G033 | 1.000 | 13 | 12 | 0 | 0 | 2.27 | — |
| G034 | 1.000 | 13 | 12 | 0 | 0 | 2.175 | — |
| G035 | 1.000 | 13 | 12 | 0 | 0 | 2.247 | — |
| G036 | 0.500 | 13 | 12 | 0 | 0 | 2.315 | 492 F.3d 551 |
| G037 | 1.000 | 14 | 13 | 0 | 0 | 2.352 | — |
| G038 | 1.000 | 12 | 11 | 0 | 0 | 2.209 | — |
| G039 | 0.000 | 12 | 12 | 0 | 0 | 2.082 | 401 U.S. 424 |
| G040 | 1.000 | 14 | 13 | 0 | 0 | 2.311 | — |
| G041 | 0.000 | 12 | 12 | 0 | 0 | 2.223 | 411 U.S. 792, 349 F.3d 634 |
| G042 | 1.000 | 13 | 12 | 0 | 0 | 2.159 | — |
| G043 | 1.000 | 12 | 12 | 0 | 0 | 2.186 | — |
| G044 | 1.000 | 13 | 12 | 0 | 0 | 2.358 | — |
| G045 | 1.000 | 13 | 13 | 0 | 0 | 2.793 | — |
| G046 | 1.000 | 13 | 13 | 0 | 0 | 2.524 | — |
| G047 | 1.000 | 13 | 13 | 0 | 0 | 2.527 | — |
| G048 | 1.000 | 14 | 14 | 0 | 0 | 2.906 | — |
| G049 | 1.000 | 12 | 12 | 0 | 0 | 2.445 | — |
| G050 | 0.500 | 13 | 13 | 0 | 0 | 2.369 | 524 U.S. 742 |
| G051 | 1.000 | 13 | 13 | 0 | 0 | 2.51 | — |
| G052 | 1.000 | 12 | 12 | 0 | 0 | 2.403 | — |
| G053 | 0.000 | 13 | 13 | 0 | 0 | 2.571 | 524 U.S. 775, 532 U.S. 268 |
| G054 | 1.000 | 13 | 13 | 0 | 0 | 2.77 | — |
| G055 | 1.000 | 13 | 13 | 0 | 0 | 2.653 | — |
| G056 | 0.500 | 14 | 14 | 0 | 0 | 2.56 | 419 F.3d 885 |
| G057 | 0.500 | 12 | 12 | 0 | 0 | 2.572 | 510 U.S. 17 |
| G058 | 1.000 | 13 | 13 | 0 | 0 | 2.557 | — |
| G059 | 1.000 | 14 | 14 | 0 | 0 | 2.538 | — |
| G060 | 1.000 | 12 | 12 | 0 | 0 | 2.428 | — |
| G061 | 1.000 | 13 | 13 | 0 | 0 | 1.379 | — |
| G062 | 1.000 | 12 | 12 | 0 | 0 | 1.347 | — |
| G063 | 1.000 | 14 | 13 | 0 | 0 | 1.501 | — |
| G064 | 1.000 | 12 | 12 | 0 | 0 | 1.295 | — |
| G065 | 1.000 | 15 | 15 | 0 | 0 | 1.666 | — |
| G066 | 1.000 | 13 | 13 | 0 | 0 | 1.599 | — |
| G067 | 1.000 | 13 | 12 | 0 | 0 | 2.348 | — |
| G068 | 1.000 | 14 | 13 | 0 | 0 | 2.219 | — |
| G069 | 1.000 | 14 | 13 | 0 | 0 | 2.22 | — |
| G070 | 1.000 | 13 | 12 | 0 | 0 | 2.286 | — |
| G071 | 1.000 | 18 | 18 | 0 | 0 | 2.018 | — |
| G072 | 1.000 | 13 | 12 | 0 | 0 | 2.087 | — |
| G073 | 1.000 | 12 | 12 | 0 | 0 | 2.082 | — |
| G074 | 1.000 | 13 | 12 | 0 | 0 | 1.603 | — |
| G075 | 1.000 | 13 | 13 | 0 | 0 | 1.618 | — |
| G076 | 0.500 | 13 | 12 | 0 | 0 | 1.677 | 534 U.S. 184 |
| G077 | 1.000 | 13 | 12 | 0 | 0 | 1.685 | — |
| G078 | 1.000 | 13 | 12 | 0 | 0 | 1.675 | — |
| G079 | 1.000 | 14 | 13 | 0 | 0 | 2.082 | — |
| G080 | 1.000 | 12 | 11 | 0 | 0 | 1.847 | — |
| G081 | 0.500 | 10 | 10 | 0 | 0 | 1.487 | 42 U.S.C. § 12112 |
| G082 | 1.000 | 10 | 10 | 0 | 0 | 1.279 | — |
| G083 | 1.000 | 11 | 11 | 0 | 0 | 1.457 | — |
| G084 | 1.000 | 9 | 9 | 0 | 0 | 1.267 | — |
| G085 | 1.000 | 10 | 10 | 0 | 0 | 1.292 | — |
| G086 | 1.000 | 13 | 12 | 0 | 0 | 1.756 | — |
| G087 | 1.000 | 13 | 12 | 0 | 0 | 1.699 | — |
| G088 | 1.000 | 15 | 15 | 0 | 0 | 1.384 | — |
| G089 | 1.000 | 9 | 9 | 0 | 0 | 1.4 | — |
| G090 | 1.000 | 12 | 11 | 0 | 0 | 2.262 | — |
| G091 | 1.000 | 12 | 11 | 0 | 0 | 2.149 | — |
| G092 | 1.000 | 12 | 11 | 0 | 0 | 2.221 | — |
| G093 | 1.000 | 12 | 11 | 0 | 0 | 2.104 | — |
| G094 | 1.000 | 13 | 12 | 0 | 0 | 1.69 | — |
| G095 | 1.000 | 13 | 12 | 0 | 0 | 2.223 | — |
| G096 | 1.000 | 12 | 11 | 0 | 0 | 2.331 | — |
| G097 | 1.000 | 12 | 11 | 0 | 0 | 2.146 | — |
| G098 | 1.000 | 12 | 11 | 0 | 0 | 2.049 | — |
| G099 | 0.000 | 12 | 11 | 0 | 0 | 2.416 | 530 U.S. 133, 309 F.3d 893 |
| G100 | 0.000 | 12 | 11 | 0 | 0 | 2.134 | 29 U.S.C. § 631 |
