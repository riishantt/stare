// Mirrors backend/stare/schemas.py and backend/stare/api/schemas_api.py

export type Role = "attorney" | "paralegal" | "admin";

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  active: boolean;
  created_at?: string | null;
}
export interface TokenOut {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Court {
  id: string;
  name: string;
  short_name: string;
  level: string;
  circuit?: string | null;
  state?: string | null;
}

export type Statute = "title_vii" | "ada" | "adea";
export interface Claim {
  statute: Statute;
  theory: string;
  description: string;
}
export interface Party {
  role: "plaintiff" | "defendant" | "other";
  name: string;
}
export interface KeyDate {
  label: string;
  date: string;
}
export interface CaseRecord {
  court_id?: string | null;
  court_name?: string | null;
  circuit?: string | null;
  parties: Party[];
  claims: Claim[];
  key_dates: KeyDate[];
  procedural_posture: string;
  facts_summary: string;
  redaction_count: number;
  client_side: "plaintiff" | "defendant";
}

export interface PlanItem {
  id: string;
  issue: string;
  statute?: Statute | null;
  elements: string[];
  queries: string[];
  checked: boolean;
}
export interface ResearchPlan {
  question: string;
  court_id?: string | null;
  items: PlanItem[];
  include_adverse: boolean;
  instructions: string;
  approved_by?: number | null;
  approved_at?: string | null;
}

export type AuthorityStatus = "binding" | "persuasive" | "flagged";
export interface AuthorityRank {
  status: AuthorityStatus;
  weight: number;
  reason: string;
}

export type GateOutcome = "pass" | "warn" | "fail" | "skip" | "unresolved";
export type CheckStatus = "verified" | "warning" | "blocked" | "unresolved";
export interface GateResult {
  gate: 1 | 2 | 3 | 4;
  name: "extract" | "exists" | "quote_match" | "good_law";
  outcome: GateOutcome;
  detail: string;
  score?: number | null;
}
export interface ExtractedCitation {
  raw: string;
  cite: string;
  case_name: string;
  year?: number | null;
  court_hint?: string | null;
  quote: string;
  pin_cite?: string | null;
  kind: string;
  span?: [number, number];
}
export interface CitationCheck {
  citation: ExtractedCitation;
  gates: GateResult[];
  status: CheckStatus;
  reason: string;
  opinion_id?: number | null;
  matched_case_name?: string | null;
  source?: string | null;
  url?: string | null;
  treatment: string[];
  phase?: "candidates" | "adverse" | "memo" | string;
}

export interface Authority {
  key: string;
  kind: "case" | "statute" | "regulation";
  citation: string;
  case_name: string;
  court_id?: string | null;
  court_name?: string | null;
  year?: number | null;
  date_filed?: string | null;
  url?: string | null;
  opinion_id?: number | null;
  section_id?: number | null;
  rank?: AuthorityRank | null;
  proposition: string;
  quote: string;
  plan_item_id?: string | null;
  adverse: boolean;
  adverse_reason: string;
  verification?: CitationCheck | null;
}

export interface MemoCitation {
  marker: string;
  citation: string;
  case_name: string;
  url?: string | null;
  authority_key?: string | null;
  status: CheckStatus;
}
export interface Memo {
  title: string;
  question_presented: string;
  issue: string;
  rule: string;
  application: string;
  conclusion: string;
  adverse_authority: string;
  warnings: string[];
  citations: MemoCitation[];
  removed_citations: string[];
  disclaimer: string;
  generated_by: string;
}

export type AgentName =
  | "orchestrator"
  | "intake"
  | "research"
  | "precedent"
  | "opposing_counsel"
  | "citation_firewall"
  | "memo"
  | "export";
export type StepStatus = "waiting" | "running" | "done" | "error" | "skipped";
export interface TraceEvent {
  run_id?: number;
  agent: AgentName;
  status: StepStatus;
  summary: string;
  started_at?: string | null;
  ended_at?: string | null;
  duration_ms?: number | null;
  data: Record<string, unknown>;
  seq: number;
}

export type RunStatus =
  | "intake_running"
  | "awaiting_plan_approval"
  | "researching"
  | "awaiting_memo_approval"
  | "approved"
  | "exported"
  | "failed"
  | "cancelled"
  | string;

export interface RunOut {
  id: number;
  case_id: number;
  status: RunStatus;
  case_record: CaseRecord | null;
  plan: ResearchPlan | null;
  authorities: Authority[];
  adverse: Authority[];
  checks: CitationCheck[];
  memo: Memo | null;
  memo_version?: number | null;
  memo_approved_by?: number | null;
  memo_approved_at?: string | null;
  steps: TraceEvent[];
  latency_ms?: number | null;
  cost_usd: number;
  llm_provider: string;
  created_at?: string | null;
  plan_approved_by?: number | null;
  plan_approved_at?: string | null;
  loop_count: number;
  error?: string | null;
}

export interface EntityOut {
  entity_type: string;
  placeholder: string;
  start?: number | null;
  end?: number | null;
}
export interface DocumentOut {
  id: number;
  file_name: string;
  page_count: number;
  ocr_used: boolean;
  redacted_text: string;
  redaction_count: number;
  entities: EntityOut[];
  redaction_engine: string;
  created_at?: string | null;
}
export interface MatterSummary {
  id: number;
  matter_number: string;
  title: string;
  court_id?: string | null;
  court_name?: string | null;
  claims: { statute?: string; theory?: string }[];
  status: string;
  created_at?: string | null;
  last_run_status?: string | null;
  document_count: number;
}
export interface RunBrief {
  id: number;
  status: RunStatus;
  created_at?: string | null;
  llm_provider: string;
}
export interface MatterDetail extends MatterSummary {
  notes: string;
  case_record?: CaseRecord | null;
  documents: DocumentOut[];
  runs: RunBrief[];
}

export interface GraphNode {
  id: string;
  label: string;
  citation: string;
  status?: string | null;
  check_status?: string | null;
  court?: string | null;
  year?: number | null;
  adverse: boolean;
}
export interface GraphEdge {
  source: string;
  target: string;
  treatment?: string | null;
}
export interface GraphOut {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface OpinionOut {
  id: number;
  case_name: string;
  citation: string;
  court?: string | null;
  court_id?: string | null;
  date_filed?: string | null;
  url?: string | null;
  text: string;
}

export interface FirewallCheckOut {
  checks: CitationCheck[];
  summary: string;
  counts: Record<string, number>;
  exportable: boolean;
  cleaned_text: string;
  removed: string[];
  redaction_count: number;
}

export interface AuditRow {
  id: number;
  at: string;
  user_id?: number | null;
  user_name?: string | null;
  action: string;
  entity: string;
  entity_id?: number | null;
  detail: Record<string, unknown>;
}
export interface SettingsOut {
  retention_days: number;
  llm_provider: string;
  model: string;
  fast_model?: string;
}
export interface Health {
  status: string;
  version: string;
  llm_provider: string;
  corpus: Record<string, number>;
  index_built?: boolean;
}
