# STARE module contracts

This file is the source of truth for the interfaces between modules. Every module is built against
it, and any change to it must be made deliberately. The shared types live in
`backend/stare/schemas.py` (domain objects), `backend/stare/db/models.py` (tables),
`backend/stare/agents/state.py` (LangGraph state) and `backend/stare/llm/` (chat models).

## Ground rules (apply to every module)

1. **$0 operation.** Nothing calls a paid API. The LLM provider defaults to `offline`. Every agent
   has a deterministic path for `llm.is_offline`. Tests never hit paid endpoints. Free public
   endpoints (static.case.law, CourtListener anonymous API) may be used by ingest scripts, and by
   tests marked `@pytest.mark.network` only.
2. **Laptop-friendly.** 8 GB RAM. No neural model is downloaded or run by default. Heavy paths
   (fastembed, sentence-transformers, cross-encoders, bulk CourtListener import, PostgreSQL) are
   implemented behind config switches but are not exercised by default tests.
3. **SQLite and PostgreSQL.** Use SQLAlchemy 2.0 ORM via `stare.db.session_scope()` /
   `get_sessionmaker()`. Do not use dialect-specific SQL, except in clearly separated
   `if settings.is_postgres:` branches (e.g. a pgvector `<=>` search).
4. **No raw client text** is stored in the DB or logs. Only redacted text is stored.
5. **Python 3.12**, venv at `backend/.venv`. Run tests with `cd backend && .venv/bin/pytest`.
   Tests use a temporary data dir: the `settings`/`db` fixtures in `tests/conftest.py` set
   `STARE_DATA_DIR` to a tmp path and clear the settings cache.
6. Every agent and every Firewall gate is its own module with unit tests (NFR-08).

---

## 1. Courts — `stare/courts/hierarchy.py`

```python
class CourtHierarchy:
    @classmethod
    def default(cls) -> "CourtHierarchy"            # loads data/courts.json (all federal courts, CourtListener ids)
    def get(self, court_id: str) -> Court | None
    def all(self) -> list[Court]
    def circuit_of(self, court_id: str) -> str | None
    def normalize(self, text: str) -> str | None     # "N.D. Tex." / "Northern District of Texas" / "5th Cir." -> court id

class AuthorityRanker:
    def __init__(self, hierarchy: CourtHierarchy | None = None)
    def rank(self, deciding_court_id: str | None, filing_court_id: str | None, *, published: bool = True,
             negative_treatment: bool = False) -> AuthorityRank
```

Table 26 weights for a matter in N.D. Tex.: SCOTUS = binding 1.0; own-circuit published = binding
0.9; own-circuit unpublished = persuasive 0.6; district courts in the same circuit = persuasive 0.5
(the same district is also persuasive 0.5, because district decisions never bind); other-circuit
published = persuasive 0.4; other-circuit unpublished = persuasive 0.3; district courts outside the
circuit = persuasive 0.3; negative treatment = `flagged`, weight 0.0, reason "Gate 4 warning: not
used until reviewed". The reason string is human readable, e.g. "Court of appeals for Texas (Fifth
Circuit), published". Unknown courts are persuasive 0.2.

## 2. Ingest — `stare/ingest/`

- `cap.py`: `fetch_cap_case(reporter_slug, volume, page) -> dict | None` (static.case.law JSON), and
  `import_cap_case(session, case_json) -> Opinion` (creates Opinion + Citation rows for official and
  parallel cites; stores `cites_to` for edges). Also `import_cap_bulk(path)` for a downloaded
  reporter volume directory (heavy path, not run by default).
- `courtlistener_bulk.py`: streaming importer for CourtListener bulk CSVs (courts, opinions,
  citations, citation map) filtered to employment-law opinions. It never loads a whole file into
  memory. Implemented and unit tested on tiny fixtures; **not run** on the laptop.
- `statutes.py`: import US Code sections (Title VII 42 U.S.C. 2000e–2000e-17, ADA Title I and
  definitions 42 U.S.C. 12101–12117, ADEA 29 U.S.C. 621–634) and eCFR parts (29 C.F.R. 1601, 1625,
  1630) into `StatuteSection`.
- `seed.py`: builds the **seed corpus** from `data/seed/manifest.json`, a curated list of real
  employment cases. It fetches each case from CAP static (or CourtListener for post-2018 cases), checks
  that the case name matches, and caches the raw JSON under `data/seed/raw/`, which is committed so a
  fresh clone builds offline. It builds citation edges among seed opinions and loads
  `data/seed/treatments.json` (curated negative treatment, e.g. Toyota v. Williams superseded by the
  ADAAA 2008).
- `chunker.py`: `chunk_text(text, max_tokens, overlap) -> list[tuple[int, str]]` (char_start, text),
  paragraph-aware.
- `pipeline.py`: `build_corpus(session, *, offline_only: bool)` = courts + seed + statutes + chunks
  + retrieval index build. CLI: `stare ingest seed`, `stare ingest statutes`, `stare index build`.

## 3. Retrieval — `stare/retrieval/`

```python
class Embedder(Protocol):                       # embed.py
    dim: int
    def fit(self, texts: list[str]) -> None     # LSA needs fitting; neural embedders no-op
    def embed(self, texts: list[str]) -> np.ndarray   # (n, dim) float32, L2-normalised
    def save(self, path: Path) -> None; @classmethod load(cls, path) -> "Embedder"
def get_embedder(settings) -> Embedder          # "lsa" (TF-IDF + TruncatedSVD, default), "fastembed", "sentence_transformers"

class BM25Index:                                # bm25.py — own Okapi BM25 (k1=1.5, b=0.75), legal-aware tokenizer
    def build(self, ids: list[int], texts: list[str]) -> None
    def search(self, query: str, k: int) -> list[tuple[int, float]]
    def save(path) / load(path)

def rrf(rankings: list[list[int]], k: int = 60) -> list[tuple[int, float]]   # rrf.py

class Reranker(Protocol):                       # rerank.py — "lexical" default, "cross_encoder" optional
    def rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]

class HybridRetriever:                          # hybrid.py
    def __init__(self, session_factory, settings=None)
    @classmethod
    def build_index(cls, session) -> None       # fit embedder, embed all chunks, store embeddings, build BM25, save to settings.index_dir
    def search(self, query: str, k: int = 30, *, kinds: set[str] | None = None,
               court_ids: set[str] | None = None) -> list[RetrievedChunk]  # BM25 + dense -> RRF -> rerank
    def search_many(self, queries: list[str], k: int = 30, **kw) -> list[RetrievedChunk]   # RAG-Fusion across queries
    def authorities_from_chunks(self, chunks: list[RetrievedChunk], limit: int) -> list[Authority]  # group by opinion/section
```

Dense search uses numpy brute force on SQLite and pgvector `<=>` on PostgreSQL.

## 4. Citation Firewall — `stare/citations/`

```python
# parser.py — Gate 1
def extract_citations(text: str) -> list[ExtractedCitation]   # eyecite: full, short-form, id., statutes; attaches quoted text near the cite and the case name

# index.py
class CitationIndex:
    def __init__(self, session)
    def lookup(self, volume: str, reporter: str, page: str) -> list[Opinion]   # normalised reporter
    def lookup_statute(self, cite: ExtractedCitation) -> StatuteSection | None
    def opinion_text(self, opinion_id: int) -> str

# courtlistener.py
class CourtListenerClient:                      # rate limited (token bucket), disk cache under cache_dir/courtlistener
    def __init__(self, settings)
    def lookup_citation(self, volume, reporter, page) -> list[dict] | None   # None = API unavailable (NFR-06); [] = not found
    def fetch_opinion_text(self, cluster_id: int) -> str | None
    def citing_opinions(self, cluster_id: int, limit: int = 50) -> list[dict] | None
    quota_left: int

# gates.py — one function per gate, each returns GateResult
def gate_extract(cite: ExtractedCitation) -> GateResult
def gate_exists(cite, index, client) -> tuple[GateResult, OpinionRef | None]  # volume/reporter/page AND case-name similarity >= case_name_threshold
def gate_quote_match(quote: str, opinion_text: str, settings) -> GateResult   # exact (normalised) pass; >= 0.90 warn; lower fail; no quote -> skip
def gate_good_law(opinion_id, session, client) -> GateResult                 # Treatment rows + citing-case context scan for overruled/abrogated/superseded

# firewall.py
class CitationFirewall:
    def __init__(self, session_factory, settings=None, client: CourtListenerClient | None = None)
    def verify_citation(self, cite: ExtractedCitation) -> CitationCheck
    def verify_text(self, text: str) -> list[CitationCheck]
    def verify_authority(self, a: Authority) -> CitationCheck   # builds an ExtractedCitation from the Authority (+ its quote)
    def filter_text(self, text: str, checks: list[CitationCheck]) -> tuple[str, list[str]]  # removes blocked/unresolved citation sentences; returns (clean_text, removed)
```

Status rules: Gate 2 fail or Gate 3 fail → `blocked`. Gate 2 unresolved (API down and not in the
local index) → `unresolved` (never exportable). Gate 3 warn or Gate 4 warn → `warning` (shown to the
attorney, never removed silently). Otherwise → `verified`. The six Mata v. Avianca fabrications must
all be `blocked` (test: `tests/test_mata_fixture.py`). Statute citations are verified against
`StatuteSection`.

## 5. Intake — `stare/intake/`

```python
def extract_document(data: bytes, file_name: str) -> ExtractedDocument   # pdf_reader.py: PyMuPDF; Tesseract OCR for pages with < 40 chars of text; .txt/.docx also accepted
class PIIRedactor:                                                       # redactor.py
    def __init__(self, engine: Literal["auto","presidio","regex"] = "auto")
    def redact(self, text: str, *, keep: set[str] = frozenset()) -> RedactionResult   # placeholders [PERSON_1], consistent per entity value
    def redact_edited(self, text: str, known_types: dict[str, str] | None = None) -> RedactionResult  # hand-corrected text: new placeholders numbered after existing ones; kept ones still counted
def extract_case_record(redacted_text: str, llm: ChatModel, hierarchy: CourtHierarchy) -> CaseRecord  # extractor.py: rules (offline) or LLM JSON
def draft_plan(record: CaseRecord, llm: ChatModel) -> ResearchPlan       # planner.py: element templates per statute/theory (offline) or LLM
```

`data/samples/` holds synthetic complaint PDFs (one text PDF and one scanned/image-only PDF) for N.D.
Tex. and N.D. Cal., plus a seeded-PII text set for the redaction coverage test.

## 6. Agents and orchestrator — `stare/agents/`, `stare/graph/`

```python
class BaseAgent(ABC):
    name: AgentName
    def __init__(self, deps: AgentDeps)     # deps: llm, session_factory, retriever, firewall, hierarchy, settings, emit
    def run(self, state: ResearchState) -> dict   # returns a partial state update
```

Agents: `IntakeAgent`, `ResearchAgent`, `PrecedentAgent`, `OpposingCounselAgent`,
`FirewallAgent` (wraps CitationFirewall), `MemoAgent`.

Graph (`stare/graph/orchestrator.py`): `intake → plan_gate (interrupt) → research → precedent →
opposing_counsel → firewall → [verified < min and loops < 3 → research] → memo → memo_firewall →
memo_gate (interrupt) → [changes requested → memo] → END`. The checkpointer is SqliteSaver (`settings.checkpoint_path`),
or PostgresSaver when on PostgreSQL.

```python
class ResearchService:                     # stare/graph/service.py — the only thing the API calls
    def __init__(self, session_factory, settings=None, llm=None)
    def start_run(self, case_id: int, user_id: int) -> int                       # creates ResearchRun, runs intake, stops at plan gate
    def update_case_record(self, run_id, record: CaseRecord, user_id) -> None    # also redrafts the plan from the record
    def approve_plan(self, run_id: int, plan: ResearchPlan, user_id: int) -> None   # resumes graph; runs to memo gate
    def request_memo_changes(self, run_id: int, instruction: str, user_id: int) -> None
    def approve_memo(self, run_id: int, memo: Memo | None, user_id: int) -> None    # optional edits: prose fields only, re-checked by the Firewall
    def cancel(self, run_id: int, user_id: int) -> None
    def export_docx(self, run_id: int, user_id: int) -> bytes                     # refuses unless approved and 0 non-exportable citations
    def subscribe(self, run_id: int) -> EventSubscription                        # thread-safe queue of TraceEvent dicts + {"type":"status"}
```

Gate actions move the run's status with a compare-and-set update (`RunStateError`/409 if another
request got there first). Long steps run in a worker thread. Each agent emits `TraceEvent`s (running → done) through
`stare/graph/events.py:EventBus`, and these are persisted as `AgentStep` rows.

## 7. Export — `stare/export/docx_exporter.py`

`class MemoExporter: def to_docx(self, memo: Memo, run_meta: dict) -> bytes`. This produces an
editable Word memo with a header block, IRAC headings, numbered citations with hyperlinks, the
adverse-authority section, the Firewall warnings, a verification appendix (one row per citation:
status and gates) and the disclaimer footer.

## 8. HTTP API — `stare/api/` (FastAPI, prefix `/api`)

Auth: JWT bearer. `POST /api/auth/login {email,password} -> {access_token, token_type, user}`,
`GET /api/auth/me`. Roles: `attorney`, `paralegal`, `admin`. The SSE endpoint accepts
`?token=` because EventSource cannot send headers.

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | /api/health | any | `{status, version, llm_provider, corpus: {opinions, statutes, chunks}, index_built}` |
| GET | /api/courts | auth | list of Court |
| GET/POST | /api/users | admin | create `{name,email,password,role}` |
| PATCH | /api/users/{id} | admin | role/active/password |
| GET | /api/matters | auth | list `MatterSummary` |
| POST | /api/matters | attorney, paralegal | `{title, court_id?, notes?}` |
| GET | /api/matters/{id} | auth | `MatterDetail` with documents and runs |
| POST | /api/matters/{id}/documents | attorney, paralegal | multipart `file`; returns `DocumentOut` (redacted text + entities) |
| PATCH | /api/documents/{id} | attorney, paralegal | `{redacted_text}` correction (human review point 2); re-redacted with `redact_edited` |
| POST | /api/matters/{id}/runs | attorney, paralegal | starts a run (intake → plan gate); returns `RunOut` |
| GET | /api/runs/{id} | auth | `RunOut` |
| PUT | /api/runs/{id}/case-record | attorney, paralegal | edit extracted facts; typed text is redacted and the plan is redrafted |
| POST | /api/runs/{id}/plan/approve | **attorney** | body `ResearchPlan` (possibly edited) |
| POST | /api/runs/{id}/memo/changes | **attorney** | `{instruction}` (redacted before it reaches the Memo Agent) |
| POST | /api/runs/{id}/memo/approve | **attorney** | optional edited `Memo`: only the prose sections are taken; 422 with `problems` if an edit adds a failing citation |
| POST | /api/runs/{id}/cancel | attorney | |
| GET | /api/runs/{id}/events | auth (token query) | SSE: `event: trace` (TraceEvent) and `event: status` (`{status}`); replays persisted steps first |
| GET | /api/runs/{id}/export.docx | **attorney** | 409 unless approved and the export check passes; writes audit |
| GET | /api/runs/{id}/graph | auth | precedent graph `{nodes:[{id,label,citation,status,court,year,adverse}], edges:[{source,target,treatment}]}` |
| GET | /api/opinions/{id} | auth | `{id, case_name, citation, court, date_filed, url, text}` |
| POST | /api/firewall/check | auth | `{text}` → `{checks: CitationCheck[], summary, counts, exportable, cleaned_text, removed, redaction_count}`: standalone "check a draft or brief" (e.g. paste the Mata brief); text passes the PII redactor first; audited |
| GET | /api/audit | admin | filters `run_id, user_id, action, limit` |
| GET/PATCH | /api/settings | admin | `{retention_days, llm_provider (read-only display), model}` |

`RunOut = {id, case_id, status, case_record, plan, authorities, adverse, checks, memo, steps,
latency_ms, cost_usd, llm_provider, created_at, plan_approved_by, plan_approved_at, error}`.

## 9. Evaluation — `stare/eval/`

`data/eval/gold.jsonl` (about 100 questions: `{id, question, court_id, statute, theory,
expected_citations: [...], notes}`, where every expected citation exists in the seed corpus);
`data/eval/mata_citations.json`; `stare eval run` computes retrieval recall@10, citation accuracy
(verified share of cited authorities, against the index), hallucination rate (non-verified share in
the final memo), Mata block rate, unverified-in-export, redaction coverage and latency p95. It writes
`docs/evaluation/results.md` + JSON. `stare eval baseline` (plain LLM, no retrieval) exists but needs a
paid/local LLM and is not run by default.
