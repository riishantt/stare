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
questions, with the agents calling a free OpenRouter model (the workflow refuses any model id not ending in `:free`).
A failed model call is not an error: the agent falls back to its offline path, and the result says so.

| Model (run) | LLM calls | Failed calls | Memos drafted by the LLM | Recall@10 | Hallucination rate | Unverified in export | Latency p95 |
|---|---|---|---|---|---|---|---|
| `minimax/minimax-m3.1-flash:free` (39427524318) | 21 | 12 | 0 of 3 (offline fallback) | 1.000 | 0.000 | 0 | — |
| `nvidia/nemotron-3-ultra-550b-a55b:free` (39429277783) | 36 | 7 | 3 of 3 | 1.000 | 0.125 | 0 | 228.8 s |

- With Nemotron, the model proposed 48 citations across the three memos; 6 (all in G003) failed the Citation
  Firewall and were removed before export. The hallucination rate (0.125) measures what the model proposed; the
  Firewall kept every one of those 6 out of the exported memo, so unverified citations in export stay at 0.
- The 7 failed Nemotron calls were small structured-output steps (`_Reason`, `_Counter`) where the model returned
  invalid JSON; each fell back to the offline path. The MiniMax run predates failure-reason logging.
- Latency is far above the 90 s target because free models are slow and rate limited; it is not a measure of the
  pipeline itself (offline p95 is about 1–3 s).
