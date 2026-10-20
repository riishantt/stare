# Cloud evaluation runs

Produced by the **Evaluate** GitHub Actions workflow (`.github/workflows/evaluate.yml`), run 39044011910
on 17 October 2026, on all 100 gold questions in offline LLM mode. These are the configurations that are
too heavy for the development laptop.

| Configuration | Recall@10 | Citation accuracy | Hallucination rate | Unverified in export | Mata | Latency p95 |
|---|---|---|---|---|---|---|
| SQLite + LSA (laptop default, `../results.md`) | 0.860 | 1.000 | 0.000 | 0 | 6 of 6 | 1.18 s |
| PostgreSQL 16 + pgvector + LSA | 0.865 | 1.000 | 0.000 | 0 | 6 of 6 | 2.73 s |
| SQLite + fastembed (bge-small) | 0.885 | 1.000 | 0.000 | 0 | 6 of 6 | 3.09 s |
| PostgreSQL 16 + pgvector + fastembed | 0.885 | 1.000 | 0.000 | 0 | 6 of 6 | 3.35 s |

Latency includes the cloud machine's slower CPU. Every target in Table 29 is met in every configuration.

## Mata fixture with a CourtListener token

**Mata check** workflow, run 39051552124 (17 October 2026), with the free CourtListener API token as a repository
secret. With the authenticated citation lookup, all six fabricated citations are **blocked** (without a token,
three are blocked and three are unresolved; both outcomes are non-exportable):

| Fabricated citation | Status |
|---|---|
| 925 F.3d 1339 (Varghese) | blocked |
| 2013 IL App (1st) 111279-U (Shaboon) | blocked |
| 905 F. Supp. 2d 121 (Petersen) | blocked |
| 2019 WL 4639462 (Martinez) | blocked |
| 2017 WL 2418825 (Estate of Durden) | blocked |
| 174 F.3d 366 (Miller) | blocked |

## LLM mode with free OpenRouter models

**Evaluate with a live LLM** workflow (`.github/workflows/evaluate-llm.yml`), 20 October 2026, on the first 3 gold
questions (and then the first 20 with Nemotron), with the agents calling a free OpenRouter model (the workflow refuses any model id not ending in `:free`).
A failed model call is not an error: the agent falls back to its offline path, and the result says so.

| Model (run) | LLM calls | Failed calls | Memos drafted by the LLM | Recall@10 | Hallucination rate | Unverified in export | Latency p95 |
|---|---|---|---|---|---|---|---|
| `minimax/minimax-m3.1-flash:free` (39427524318) | 21 | 12 | 0 of 3 (offline fallback) | 1.000 | 0.000 | 0 | — |
| `nvidia/nemotron-3-ultra-550b-a55b:free` (39429277783) | 36 | 7 | 3 of 3 | 1.000 | 0.125 | 0 | 228.8 s |
| `nvidia/nemotron-3-ultra-550b-a55b:free`, **20 questions** (39484423451) | 218 | 61 | 19 of 20 | 0.850 | 0.079 | 0 | 239.0 s |

- With Nemotron, the model proposed 48 citations across the three memos; 6 (all in G003) failed the Citation
  Firewall and were removed before export. The hallucination rate (0.125) measures what the model proposed; the
  Firewall kept every one of those 6 out of the exported memo, so unverified citations in export stay at 0.
- The 7 failed Nemotron calls were small structured-output steps (`_Reason`, `_Counter`) where the model returned
  invalid JSON; each fell back to the offline path. The MiniMax run predates failure-reason logging.
- Latency is far above the 90 s target because free models are slow and rate limited; it is not a measure of the
  pipeline itself (offline p95 is about 1–3 s).

### 20-question run (Nemotron 3 Ultra, run 39484423451)

- 19 of 20 memos were drafted by the model; G010 fell back to the offline drafter.
- The model proposed 365 citations; the Citation Firewall removed 29 (hallucination rate 0.079) and kept 336, all of
  them verified (30 with a warning shown in the memo). Unverified citations in exported memos: 0. Mata: 6 of 6 blocked.
- All 61 failed calls (28% of 218) returned output that was not valid JSON for the step: 44 + 11 in the adverse-reason
  step (`_Reason`), 3 in counter-search queries, and one each in query writing, plan drafting and memo drafting.
  Each of those steps used its offline path.
- Recall@10 was 0.850, against 0.775 for the offline mode on the same 20 questions (`../results.json`): the model's
  extra search queries help retrieval.
- Latency p95 was 239.0 s (mean 146.1 s), above the 90 s target, because the free model is slow and rate limited.
