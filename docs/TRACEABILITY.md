# Requirements traceability

This file maps every requirement in the proposal (Tables 9, 10, 11, 30 and 31) to where it is
implemented and how it is verified. Paths are relative to `backend/` unless noted.

## Functional requirements (Table 10)

| ID | Requirement | Priority | Implementation | Verified by |
|---|---|---|---|---|
| FR-01 | Complaint PDF; PyMuPDF text; Tesseract OCR for scanned pages | Must | `stare/intake/pdf_reader.py` (also .txt and .docx) | `tests/test_intake_reader.py` (scanned sample OCR) |
| FR-02 | Presidio redaction before any LLM call; show redacted text | Must | `stare/intake/redactor.py`; upload route stores redacted text only; `llm/base.py: assert_redacted`; UI matter page | `tests/test_redaction.py`, `test_api.py::test_document_upload_redacts_and_stores_no_raw_pii` |
| FR-03 | Structured case record (parties, claims, court, dates, posture) | Must | `stare/intake/extractor.py`, `agents/intake.py` | `tests/test_intake_extractor.py` |
| FR-04 | Draft research plan; attorney approval before research | Must | `intake/planner.py`, `intake/elements.py`; `graph/orchestrator.py: plan_gate` (interrupt) | `test_agents.py::test_full_run_with_approval_gates_and_export`, `test_api.py::test_full_run_roles_and_export` |
| FR-05 | BM25 + dense retrieval, RRF, rerank | Must | `stare/retrieval/*`, `agents/research.py` | `tests/test_retrieval_*.py` |
| FR-06 | Binding/persuasive ranking for the court of filing, with reason | Must | `courts/hierarchy.py: AuthorityRanker`, `agents/precedent.py` | `tests/test_courts.py`, `test_agents.py::test_research_then_precedent_ranking` |
| FR-07 | Four gates: extraction, existence, quote, later treatment | Must | `stare/citations/*` | `tests/test_citations_*.py`, `test_firewall.py`, `test_gate4_precision.py` |
| FR-08 | Remove Gate 2/3 failures; flag treatment warnings | Must | `CitationFirewall.filter_text`, `agents/firewall_agent.py`, `agents/memo_firewall.py` | `test_agents.py::test_check_memo_removes_hallucinated_citation`, `test_firewall.py` |
| FR-09 | IRAC memo from verified authorities only, link for every citation | Must | `agents/memo.py` (+ second Firewall pass) | `test_agents.py::test_firewall_agent_flags_superseded_case_and_memo_lists_warning` |
| FR-10 | Adverse-authority report before the memo | Should | `agents/opposing.py` (+ timeliness checks) | `test_agents.py::test_procedural_flags_detect_late_charge` |
| FR-11 | Live trace: status, timing, result | Should | `agents/base.py` (TraceEvent), `graph/events.py`, SSE `/api/runs/{id}/events`, `frontend/src/hooks/useRunEvents.ts` | `test_api.py::test_events_sse_replays_steps_and_status` |
| FR-12 | DOCX export after approval; audit entry per run and approval | Must | `export/docx_exporter.py`, `ResearchService.export_docx`, `AuditLog` | `test_export.py`, `test_agents.py::test_export_blocked_when_memo_contains_unverified_citation` |
| FR-13 | Role-based login | Should | `stare/api/auth.py` (JWT, `require_roles`) | `test_api.py::test_login_me_and_failures`, `test_full_run_roles_and_export` |
| FR-14 | Interactive precedent graph | Could | `/api/runs/{id}/graph`, `frontend/src/components/PrecedentGraph.tsx` | `test_api.py::test_graph_and_opinion` |
| FR-15 | State law, criminal law, court filing | Won't | Not in scope; `client_side` and the court registry cover federal courts only | — |

## Non-functional requirements (Table 11)

| ID | Target | How it is met | Evidence |
|---|---|---|---|
| NFR-01 | Zero failed or unresolved citations in an exported memo | The memo Firewall pass, edited-memo verification (422) and an export recheck (409) | `stare eval run` → "unverified in export"; `test_agents.py` export tests |
| NFR-02 | Memo in < 90 s (p95) | Offline pipeline ≈ 2–4 s on an M2 laptop | `docs/evaluation/results.md` latency p95 |
| NFR-03 | 100 % redaction on test documents; no raw client text stored | Upload stores redacted text only; raw bytes discarded; prompt guard | `test_redaction.py` (seeded set), results.md redaction coverage |
| NFR-04 | Every statement of law links to a verified source | Memo citations carry markers, links and status | memo view; DOCX "Authorities Cited" and appendix |
| NFR-05 | Steps, sources, gate results and approvals stored | `AgentStep`, `CitationCheckRow`, `MemoRow`, `AuditLog` | `test_api.py` audit assertions |
| NFR-06 | CourtListener unavailable → continue with the local index; mark unchecked items | The client returns `None` on any failure → `unresolved` (never exportable) | `test_citations_courtlistener.py`, `test_mata_fixture.py` |
| NFR-07 | Usable without training | Guided three-column workspace, gate prompts, disabled-with-reason buttons | frontend |
| NFR-08 | Each agent and gate is a separate module with unit tests | `stare/agents/*.py`, `citations/gates.py` | `tests/` (one file per area) |

## User stories (Table 9)

| ID | Story | Where |
|---|---|---|
| US-01 | Upload a complaint, see the extracted redacted text | Matter page → document card (edit redactions) |
| US-02 | Approve or edit the research plan | Workspace, left column: plan editor + instruction |
| US-03 | Each citation with status and a link to the opinion | Sources column: badges, gates, "View opinion" drawer |
| US-04 | Adverse authority for my court | Memo view: Adverse Authority section; Sources → Adverse tab |
| US-05 | Export the approved memo as Word | Memo view → Export DOCX (enabled after approval) |
| US-06 | Audit log of runs and approvals | Admin → Audit log |
| US-07 | Watch agent progress live | Workspace, centre column: live agent trace + 90 s progress bar |

## Product backlog (Table 30)

| PB | Item | Status |
|---|---|---|
| PB-01 | CourtListener and CAP import | Done: seed corpus built from CAP/CourtListener; bulk importers implemented and tested on fixtures |
| PB-02 | Local citation index | Done (`citations` table, reporter normalisation) |
| PB-03 | Chunking, embeddings, BM25 | Done |
| PB-04 | Hybrid search with RRF and reranker | Done |
| PB-05 | PDF intake, OCR, Presidio redaction | Done |
| PB-06 | LangGraph orchestrator, shared state, checkpoints | Done (SQLite/Postgres checkpointer) |
| PB-07 | Intake and Research agents; plan approval gate | Done |
| PB-08 | Precedent Agent and court hierarchy | Done (108 federal courts) |
| PB-09 | Firewall Gates 1–4 with Mata fixture test | Done |
| PB-10 | React interface: intake, plan approval, live trace | Done |
| PB-11 | Opposing Counsel Agent and adverse report | Done |
| PB-12 | Memo Agent, memo approval gate, DOCX export | Done |
| PB-13 | Audit log, login, roles | Done |
| PB-14 | Evaluation on the gold set; LLM baseline comparison | Done: gold set (100 questions), automated metrics, and a general-purpose LLM baseline (a free opencode model answering the same 100 questions without retrieval, scored by the same Firewall: `stare eval baseline --answers`) |
| PB-15 | Precedent graph view | Done |

## Success criteria (Table 31)

The results are in [evaluation/results.md](evaluation/results.md). Criteria 3–4: the automated numbers measure existence and quote fidelity (1.0; hallucination rate 0.0).
Whether each authority *supports* its statement was reviewed on a 20-question sample in
[evaluation/support_review.md](evaluation/support_review.md): **98.6%** of citations exist and support the
statement (target ≥ 0.94) and **1.4%** do not (target ≤ 0.02). 87.8% quote the issue's rule verbatim. This is the manual check that Table 29 specifies,
carried out by the development assistant on the team's behalf. Validation with practising lawyers is future scope (Section 7.4). Criterion 8 (higher citation accuracy than a
general-purpose LLM) was measured with a free general-purpose model on the same 100 questions; its
answers are in `data/eval/baseline_answers_opencode.jsonl` and the scores in `docs/evaluation/baseline.json`.
