# STARE evaluation results

Generated 2026-10-20T23:16:38+00:00 with LLM provider `openai_compat:nvidia/nemotron-3-ultra-550b-a55b:free`, embedder `lsa`, reranker `lexical`, on 20 gold questions (0 errors).

LLM calls: 269 answered, 18 failed, 61 retried after an unusable JSON reply; 20 of 20 memos drafted by the LLM (the others fell back to the offline drafter).

| Metric | Result | Target (Table 29) |
|---|---|---|
| Mata fixture: fabricated citations blocked | 6 of 6 non-exportable (6 blocked, 0 unresolved) | 6 of 6 |
| Unverified citations in exported memos | 0 | 0 |
| Citation accuracy (automated): kept memo citations that exist and whose quotations match, verified or warning (314 kept) | 1.000 | ≥ 0.94 |
| Citation accuracy (automated, strict): kept memo citations fully verified, no warning (288 verified, 26 warning) | 0.917 | — |
| Hallucination rate: citations the drafter wrote that the memo Firewall blocked or left unresolved (44 of 244) | 0.180 | ≤ 0.02 |
| Retrieval recall@10 | 0.875 | ≥ 0.80 |
| Redaction coverage (auto engine) | 100.0% (27/27) | 100% |
| Redaction coverage (regex-only engine) | 96.3% (26/27) | — |
| Latency, approved plan to memo (p95) | 166.741 s | < 90 s |

Notes:
- Citation counts are per occurrence. The automated accuracy is measured over the citations left in the final memos, after the Firewall removed failing ones, so it counts warnings (e.g. a near-match quotation or good-law status not checked) as accurate; the strict row counts only fully verified citations. The hallucination rate counts the citations the drafter (the LLM, or the offline extractive drafter) wrote in the issue, rule, application and conclusion, before the memo Firewall pass; the question presented and the adverse-authority list are not drafted (they come from the gold question and the Firewall-checked adverse authorities). `hallucination_rate` in results.json keeps the earlier definition for comparison with older reports.
- The manual support review and the general-purpose LLM baseline were made against the offline run, so they are reported with the offline results, not here.

## Per-question results

| Question | recall@10 | memo citations | verified | removed | export violations | latency (s) | missed expected |
|---|---|---|---|---|---|---|---|
| G001 | 1.000 | 15 | 15 | 2 | 0 | 101.329 | — |
| G002 | 1.000 | 20 | 19 | 2 | 0 | 107.823 | — |
| G003 | 1.000 | 16 | 16 | 2 | 0 | 74.525 | — |
| G004 | 1.000 | 17 | 15 | 6 | 0 | 125.52 | — |
| G005 | 1.000 | 17 | 16 | 5 | 0 | 81.908 | — |
| G006 | 1.000 | 13 | 12 | 1 | 0 | 140.267 | — |
| G007 | 1.000 | 18 | 13 | 2 | 0 | 77.802 | — |
| G008 | 1.000 | 20 | 14 | 2 | 0 | 134.771 | — |
| G009 | 1.000 | 15 | 15 | 2 | 0 | 153.231 | — |
| G010 | 1.000 | 21 | 20 | 0 | 0 | 114.03 | — |
| G011 | 1.000 | 17 | 16 | 1 | 0 | 107.154 | — |
| G012 | 0.500 | 12 | 11 | 0 | 0 | 55.748 | 492 F.3d 551 |
| G013 | 1.000 | 21 | 20 | 1 | 0 | 80.96 | — |
| G014 | 1.000 | 16 | 13 | 6 | 0 | 165.504 | — |
| G015 | 1.000 | 25 | 22 | 1 | 0 | 125.24 | — |
| G016 | 0.500 | 18 | 18 | 0 | 0 | 100.553 | 281 F.3d 1054 |
| G017 | 1.000 | 9 | 9 | 7 | 0 | 104.541 | — |
| G018 | 0.000 | 7 | 7 | 0 | 0 | 45.467 | 532 U.S. 268 |
| G019 | 1.000 | 10 | 10 | 0 | 0 | 190.248 | — |
| G020 | 0.500 | 7 | 7 | 0 | 0 | 107.168 | 530 U.S. 133 |
