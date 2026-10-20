# Cloud evaluation runs

These are the configurations that are too heavy for the development laptop, run on GitHub Actions. The numbers
below are from the runs of 20 October 2026, after the Firewall and metric fixes of that day (commit 82877b2). The
laptop default (SQLite + LSA, offline) is in [`../results.md`](../results.md).

## Configurations, 100 gold questions, offline LLM mode

**Evaluate** workflow (`.github/workflows/evaluate.yml`), run 39508681097.

| Configuration | Recall@10 | Accuracy (kept citations) | Verified, no warning | Hallucination rate (drafted) | Unverified in export | Latency p95 |
|---|---|---|---|---|---|---|
| SQLite + LSA (laptop default, `../results.md`) | 0.860 | 1.000 | 0.968 | 0.000 | 0 | 1.23 s |
| PostgreSQL 16 + pgvector + LSA | 0.865 | 1.000 | 0.968 | 0.000 | 0 | 2.58 s |
| SQLite + fastembed (bge-small) | 0.885 | 1.000 | 0.974 | 0.000 | 0 | 3.19 s |
| PostgreSQL 16 + pgvector + fastembed | 0.885 | 1.000 | 0.974 | 0.000 | 0 | 3.19 s |

Bootstrap 95% confidence intervals for recall@10 (10,000 resamples of the questions): SQLite + LSA 0.795 to 0.920;
fastembed 0.830 to 0.935. Latency includes the cloud machine's slower CPU.

## Mata fixture with a CourtListener token

With the free CourtListener API token (repository secret), the authenticated citation lookup finds no opinion at
the three Westlaw and Illinois citations, so all six fabricated citations are **blocked**: Mata check run
39051552124 (17 October), the laptop runs of 20 October, and the PostgreSQL runs above. When several jobs used the
token at the same time on 20 October, the lookup sometimes timed out for one or two of those three citations
(SQLite + fastembed run above; Mata check run 39499916814), which were then **unresolved**. Unresolved is never
exportable (NFR-06), so all six were stopped in every run.

| Fabricated citation | With the token | Without a token |
|---|---|---|
| 925 F.3d 1339 (Varghese) | blocked | blocked |
| 2013 IL App (1st) 111279-U (Shaboon) | blocked | unresolved |
| 905 F. Supp. 2d 121 (Petersen) | blocked | blocked |
| 2019 WL 4639462 (Martinez) | blocked | unresolved |
| 2017 WL 2418825 (Estate of Durden) | blocked | unresolved |
| 174 F.3d 366 (Miller) | blocked | blocked |

## LLM mode with free OpenRouter models

**Evaluate with a live LLM** workflow (`.github/workflows/evaluate-llm.yml`), on the first 20 gold questions (the
first trials used 3), with the agents calling a free OpenRouter model. The workflow refuses any model id not ending
in `:free`. A failed model call is not an error: that step falls back to its offline path, and the result says so.

| Model, run (date) | LLM calls | Failed calls | Memos drafted by the LLM | Recall@10 | Drafted citations that failed the Firewall | Unverified in export | Latency p95 |
|---|---|---|---|---|---|---|---|
| `minimax/minimax-m3.1-flash:free`, 3 questions, 39427524318 | 21 | 12 | 0 of 3 (offline fallback) | 1.000 | — | 0 | — |
| `nvidia/nemotron-3-ultra-550b-a55b:free`, 20 questions, 39484423451 (before the fixes) | 218 | 61 | 19 of 20 | 0.850 | 29 of 365 proposed (old metric) | 0 | 239.0 s |
| **`nvidia/nemotron-3-ultra-550b-a55b:free`, 20 questions, 39508675897 (final)** | 269 | 18 | **20 of 20** | **0.875** | **44 of 244 (0.180)** | **0** | **166.7 s** |

Final run (`results-llm-nemotron-3-ultra-20q-final.*`):

- The model drafted all 20 memos. Of the 244 citations it wrote into the memos' issue, rule, application and
  conclusion, 44 failed the Citation Firewall and were removed before the memo gate (hallucination rate of the raw
  model 0.180, bootstrap 95% interval 0.103 to 0.260). No unverified citation reached an export. Mata: 6 of 6 blocked.
- Of the 269 model calls, 61 unusable JSON replies were asked once more, and 18 calls (6.7%) still failed and used
  the offline path; before the JSON fix (commit 4254910) it was 61 of 218 (28%). The remaining failures are mostly the
  short adverse-reason step (`_Reason`), cut off at its token budget or returning the wrong type.
- Recall@10 was 0.875, against 0.775 in offline mode on the same 20 questions (3 questions better, none worse;
  difference 0.100, 95% interval 0.000 to 0.225). With 20 questions the gain is not established with confidence.
- Latency p95 was 166.7 s (mean 109.7 s), above the 90 s target, because the free model is slow and rate limited.
- The live model is not deterministic: the run before the fixes gave a raw rate of 0.132 on a comparable count
  (commit ad18444, not kept), so a single 20-question run gives an order of magnitude, not a precise rate.

## General-purpose LLM baseline (rescored)

`../baseline.json`: the saved answers of a free general-purpose LLM (`opencode/beam-free`, no retrieval) to the 100
questions, rescored on 20 October with the fixed Firewall: 563 citations; 550 exportable (accuracy 0.977); 7 blocked,
3 unresolved, and 3 attached to a quotation the cited opinion does not contain; accuracy over checked citations
550 / 560 = 0.982. STARE exported 0 unverified citations.
