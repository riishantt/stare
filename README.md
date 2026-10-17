# STARE: verified US employment-law research

STARE (named after *stare decisis*) is a multi-agent AI research assistant for US federal
employment-discrimination law: Title VII, the ADA and the ADEA. A paralegal uploads a complaint. An
attorney approves a research plan. Specialist agents then find, rank and challenge authority, and a
**Citation Firewall** checks every citation against real court records before the attorney sees the
IRAC memo. Nothing is exported without attorney approval.

Capstone project, Group 36, School of Computer Science Engineering and Technology, Bennett University:
Sanskar Awasthi, Rishant Ranjan, Adarsh Singh and Rahul Yadav. Supervisor: Dr. Pawan Kumar.

> Research material for licensed attorneys. Not legal advice.

## What it does

```
complaint PDF ─▶ Intake (PyMuPDF + Tesseract OCR, PII redaction) ─▶ case record + research plan
                                                  │
                                    ■ attorney approves the plan (hard gate)
                                                  ▼
 Research (BM25 + dense, RRF, rerank) ─▶ Precedent (binding / persuasive for the court of filing)
   ─▶ Opposing Counsel (adverse authority, timeliness defences)
   ─▶ Citation Firewall: Gate 1 extract · Gate 2 exists (+ case-name match) · Gate 3 quote match · Gate 4 good law
   ─▶ (too few verified? search again, max 3 loops)
   ─▶ Memo (IRAC from verified authority only) ─▶ Firewall again on the memo text
                                                  │
                                    ■ attorney approves the memo (hard gate)
                                                  ▼
                              DOCX export (refused if any citation is not verified)
```

* **Citation Firewall.** Verification is deterministic and never asks the LLM whether its own sources
  are good. All six fabricated citations from *Mata v. Avianca* are blocked (`stare eval mata`).
* **Authority ranking.** Each authority is ranked by the court hierarchy (Table 26), not only by
  similarity. A Fifth Circuit case binds N.D. Tex.; a Ninth Circuit case does not.
* **Opposing Counsel agent.** It searches only for authority that hurts the client, and it applies
  deterministic EEOC-charge timeliness checks to the extracted dates.
* **Opinion parts.** Dissents, concurrences and the Reporter's syllabus are tracked separately. STARE
  never quotes them as the court's holding, and Gate 3 warns when a quotation appears only in a dissent.
* **Human in the loop.** LangGraph interrupts at the plan gate and the memo gate. The workspace shows a
  live agent trace, and an audit log records every run, approval and export.
* **Privacy.** Personal details are redacted (Presidio + regex) before any agent runs. Only redacted
  text is stored. A guard refuses to send any prompt that still contains an SSN, email or phone number.

## Zero-cost, laptop-friendly defaults

STARE runs fully offline at $0 on an 8 GB laptop. The defaults are:

* a deterministic LLM mode
* SQLite
* LSA embeddings
* a lexical reranker
* a curated seed corpus

Each heavier option from the proposal (Claude or a local model, PostgreSQL + pgvector, neural
embeddings, a cross-encoder, bulk CourtListener import) is one setting away. See
[DECISIONS.md](DECISIONS.md).

## Quick start

Requirements: Python 3.12 (`uv` recommended), Node 20+, Tesseract (`brew install tesseract`).

```bash
# backend
cd backend
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[presidio,dev]'
.venv/bin/python -m spacy download en_core_web_sm

.venv/bin/stare ingest all --offline   # courts, seed opinions, statutes, chunks (from data/seed/raw, no network)
.venv/bin/stare index build            # BM25 + LSA dense index (≈6 s)
.venv/bin/stare db seed-users          # attorney@ / paralegal@ / admin@stare.local, password: stare-demo
.venv/bin/stare serve                  # http://127.0.0.1:8000  (OpenAPI docs at /docs)

# frontend (second terminal)
cd frontend
npm install
npm run dev                            # http://localhost:5173 (proxies /api to :8000)
```

Run the whole pipeline in the terminal, with both gates auto-approved, and save the memo as DOCX:

```bash
cd backend && .venv/bin/stare demo     # uses data/samples/complaint_ndtex_title7_retaliation.pdf
```

Sample complaints are in `data/samples/`. They include a scanned, image-only PDF that exercises OCR.
All parties and personal details in them are fictional.

## Command line

| Command | What it does |
|---|---|
| `stare ingest all [--offline]` | Build the corpus: courts, seed opinions (CAP/CourtListener), statutes and regulations, chunks |
| `stare ingest cap-bulk PATH` / `courtlistener-bulk DIR` | Import downloaded bulk data (heavy path) |
| `stare ingest refresh [--bulk-dir DIR]` | Monthly refresh: newer bulk data, new seed cases, fresh statute text, chunks and index (cron: `0 3 1 * *`) |
| `stare index build` / `stare index search "query"` | Build or query the hybrid retrieval index |
| `stare db init` / `db seed-users` / `db create-user EMAIL` | Database setup and users |
| `stare demo [PDF]` | End-to-end run in the terminal |
| `stare serve` | API server |
| `stare eval run [--limit N]` | Gold set + Mata + export check + redaction + latency → `docs/evaluation/results.md` |
| `stare eval mata` | Mata v. Avianca fixture only |
| `stare eval baseline --answers FILE` | Score a general-purpose LLM's answers (JSONL `{id, answer}`) with the Firewall; without `--answers` it calls `STARE_LLM_PROVIDER` (costs API credits) |

## Tests

```bash
cd backend && .venv/bin/pytest            # offline; tests marked `network` are skipped unless STARE_NETWORK_TESTS=1
cd frontend && npm run build              # type check + production build
```

Every agent and every Firewall gate has its own module and unit tests (NFR-08). The Mata fixture,
the approval gates and the export check are covered by automated tests.

GitHub Actions runs both on every push (`.github/workflows/ci.yml`). The **Evaluate** workflow
(`.github/workflows/evaluate.yml`, started from the Actions tab) runs the full evaluation in the cloud on
PostgreSQL 16 + pgvector and with the fastembed (bge-small) embedder, and attaches the results to the run.

## Configuration

All settings are environment variables with the `STARE_` prefix (see `backend/stare/config.py`), or
can go in `backend/.env`. Private keys go in `backend/.env.local`, which is git-ignored and overrides
`backend/.env` (see `backend/.env.example`). Tests never read those keys.

| Variable | Default | Notes |
|---|---|---|
| `STARE_LLM_PROVIDER` | `offline` | `anthropic` (Claude) or `openai_compat` (e.g. a free local Ollama server). Hosted providers cost money. |
| `STARE_LLM_MODEL` / `STARE_LLM_FAST_MODEL` | `claude-opus-5-5` / `claude-haiku-5-5` | main drafting model / routine-step model |
| `STARE_LLM_BASE_URL` | | e.g. `http://localhost:11434/v1` for Ollama |
| `STARE_DATABASE_URL` | SQLite in `data/` | `postgresql+psycopg://…` for PostgreSQL + pgvector (`docker compose up db`) |
| `STARE_EMBEDDER` | `lsa` | `fastembed`, `sentence_transformers` (then set `STARE_EMBEDDING_DIM`) |
| `STARE_RERANKER` | `lexical` | `cross_encoder` |
| `STARE_COURTLISTENER_TOKEN` | | free CourtListener token; enables the citation-lookup API fallback |
| `STARE_JWT_SECRET` | dev value | **set in any shared deployment** |

## Repository layout

```
backend/stare/
  agents/        Intake, Research, Precedent, Opposing Counsel, Firewall, Memo (+ memo Firewall pass)
  graph/         LangGraph orchestrator (approval interrupts), ResearchService, event bus
  citations/     Citation Firewall: parser (Gate 1), index, CourtListener client, gates 2-4, quote matching
  retrieval/     tokenizer, BM25, LSA/neural embedders, RRF, rerankers, HybridRetriever
  courts/        federal court hierarchy and AuthorityRanker (Table 26)
  intake/        PDF/OCR reader, PII redactor, case-record extractor, legal elements, planner
  ingest/        CAP / CourtListener (bulk + seed), US Code / eCFR, chunker
  export/        DOCX memo exporter
  api/           FastAPI app, JWT auth and roles, routers, SSE live trace
  eval/          evaluation harness and LLM baseline
frontend/src/    React research workspace (trace, sources, plan, memo editor, precedent graph, draft checker)
data/            seed corpus cache, statutes cache, court registry, samples, gold set, Mata fixture
docs/            contracts, design document, traceability, evaluation results
```

## Documentation

* [docs/DESIGN.md](docs/DESIGN.md): the design document (architecture, data model, workflow, API)
* [docs/CONTRACTS.md](docs/CONTRACTS.md): module interfaces and the HTTP API
* [docs/TRACEABILITY.md](docs/TRACEABILITY.md): proposal requirements mapped to code and tests
* [docs/evaluation/results.md](docs/evaluation/results.md): evaluation results (Table 29 metrics)
* [docs/evaluation/support_review.md](docs/evaluation/support_review.md): review of whether cited authorities support their propositions (criteria 3–4)
* [DECISIONS.md](DECISIONS.md): implementation decisions and how to switch to the heavier options

## Data sources and attribution

Case law comes from the [Caselaw Access Project](https://case.law/) (Harvard Law School Library Innovation
Lab) and [CourtListener](https://www.courtlistener.com/) (Free Law Project). Statutes come from the
[Legal Information Institute](https://www.law.cornell.edu/uscode/text) and regulations from the
[eCFR](https://www.ecfr.gov/). All are public legal data, used under the providers' terms. See
`data/seed/README.md` and `data/statutes/README.md`.
