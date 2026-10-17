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
