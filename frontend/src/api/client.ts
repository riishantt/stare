import type {
  AuditRow, Court, DocumentOut, FirewallCheckOut, GraphOut, Health, MatterDetail, MatterSummary, Memo,
  OpinionOut, ResearchPlan, CaseRecord, RunOut, SettingsOut, TokenOut, User, Role,
} from "./types";

const TOKEN_KEY = "stare.token";
const USER_KEY = "stare.user";

export const tokenStore = {
  get: () => { try { return localStorage.getItem(TOKEN_KEY); } catch { return null; } },
  set: (t: string) => { try { localStorage.setItem(TOKEN_KEY, t); } catch { /* ignore */ } },
  user: (): User | null => { try { const s = localStorage.getItem(USER_KEY); return s ? JSON.parse(s) : null; } catch { return null; } },
  setUser: (u: User) => { try { localStorage.setItem(USER_KEY, JSON.stringify(u)); } catch { /* ignore */ } },
  clear: () => { try { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); } catch { /* ignore */ } },
};

export class ApiError extends Error {
  status: number;
  problems: string[];
  constructor(status: number, message: string, problems: string[] = []) {
    super(message);
    this.status = status;
    this.problems = problems;
  }
}

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn; }

/** FastAPI errors: {detail: string | {message, problems} | [{msg}]} plus optional top-level problems. */
function parseError(status: number, body: unknown, fallback: string): ApiError {
  let message = fallback;
  let problems: string[] = [];
  if (body && typeof body === "object") {
    const b = body as Record<string, unknown>;
    const d = b.detail;
    if (typeof d === "string") message = d;
    else if (Array.isArray(d)) {
      message = d.map((x) => (typeof x === "string" ? x : (x as { msg?: string }).msg ?? JSON.stringify(x))).join("; ");
    } else if (d && typeof d === "object") {
      const o = d as Record<string, unknown>;
      if (typeof o.message === "string") message = o.message;
      else if (typeof o.detail === "string") message = o.detail;
      if (Array.isArray(o.problems)) problems = o.problems.map(String);
    }
    if (Array.isArray(b.problems)) problems = b.problems.map(String);
  }
  return new ApiError(status, message, problems);
}

async function raw(path: string, init: RequestInit = {}, isForm = false): Promise<Response> {
  const headers = new Headers(init.headers);
  const t = tokenStore.get();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  if (!isForm && init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Cannot reach the STARE server. Check that the API is running.");
  }
  if (res.status === 401 && !path.startsWith("/auth/login")) {
    tokenStore.clear();
    onUnauthorized();
  }
  if (!res.ok) {
    let body: unknown = null;
    try { body = await res.json(); } catch { /* not json */ }
    throw parseError(res.status, body, res.statusText || `Request failed (${res.status})`);
  }
  return res;
}

async function json<T>(path: string, init: RequestInit = {}, isForm = false): Promise<T> {
  const res = await raw(path, init, isForm);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const body = (b: unknown): RequestInit => ({ body: JSON.stringify(b) });

export const api = {
  login: (email: string, password: string) => json<TokenOut>("/auth/login", { method: "POST", ...body({ email, password }) }),
  me: () => json<User>("/auth/me"),
  health: () => json<Health>("/health"),
  courts: () => json<Court[]>("/courts"),

  users: () => json<User[]>("/users"),
  createUser: (u: { name: string; email: string; password: string; role: Role }) =>
    json<User>("/users", { method: "POST", ...body(u) }),
  patchUser: (id: number, p: Partial<{ name: string; role: Role; active: boolean; password: string }>) =>
    json<User>(`/users/${id}`, { method: "PATCH", ...body(p) }),

  matters: () => json<MatterSummary[]>("/matters"),
  createMatter: (m: { title: string; court_id?: string | null; notes?: string }) =>
    json<MatterSummary>("/matters", { method: "POST", ...body(m) }),
  matter: (id: number) => json<MatterDetail>(`/matters/${id}`),
  uploadDocument: (matterId: number, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return json<DocumentOut>(`/matters/${matterId}/documents`, { method: "POST", body: fd }, true);
  },
  patchDocument: (id: number, redacted_text: string) =>
    json<DocumentOut>(`/documents/${id}`, { method: "PATCH", ...body({ redacted_text }) }),

  startRun: (matterId: number) => json<RunOut>(`/matters/${matterId}/runs`, { method: "POST" }),
  run: (id: number) => json<RunOut>(`/runs/${id}`),
  putCaseRecord: (id: number, rec: CaseRecord) => json<unknown>(`/runs/${id}/case-record`, { method: "PUT", ...body(rec) }),
  approvePlan: (id: number, plan: ResearchPlan) => json<unknown>(`/runs/${id}/plan/approve`, { method: "POST", ...body(plan) }),
  requestChanges: (id: number, instruction: string) =>
    json<unknown>(`/runs/${id}/memo/changes`, { method: "POST", ...body({ instruction }) }),
  approveMemo: (id: number, memo?: Memo) =>
    json<unknown>(`/runs/${id}/memo/approve`, { method: "POST", ...(memo ? body(memo) : {}) }),
  cancelRun: (id: number) => json<unknown>(`/runs/${id}/cancel`, { method: "POST" }),
  graph: (id: number) => json<GraphOut>(`/runs/${id}/graph`),
  opinion: (id: number) => json<OpinionOut>(`/opinions/${id}`),
  async exportDocx(id: number): Promise<Blob> {
    return (await raw(`/runs/${id}/export.docx`)).blob();
  },

  firewallCheck: (text: string) => json<FirewallCheckOut>("/firewall/check", { method: "POST", ...body({ text }) }),
  audit: (q: { action?: string; run_id?: string; limit?: number }) => {
    const p = new URLSearchParams();
    if (q.action) p.set("action", q.action);
    if (q.run_id) p.set("run_id", q.run_id);
    p.set("limit", String(q.limit ?? 200));
    return json<AuditRow[]>(`/audit?${p}`);
  },
  settings: () => json<SettingsOut>("/settings"),
  patchSettings: (s: { retention_days: number }) => json<SettingsOut>("/settings", { method: "PATCH", ...body(s) }),
};

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
