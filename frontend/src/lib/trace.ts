import type { AgentName, StepStatus, TraceEvent } from "../api/types";

export interface TraceRow {
  id: string;
  agent: AgentName;
  label: string;
  status: StepStatus;
  summary: string;
  duration_ms?: number | null;
  started_at?: string | null;
  runs: number; // how many times this agent ran (loop indicator)
  placeholder: boolean;
}

const ORDER: { agent: AgentName; label: string }[] = [
  { agent: "intake", label: "Intake Agent" },
  { agent: "research", label: "Research Agent" },
  { agent: "precedent", label: "Precedent Agent" },
  { agent: "opposing_counsel", label: "Opposing Counsel" },
  { agent: "citation_firewall", label: "Citation Firewall" },
  { agent: "memo", label: "Memo Agent" },
];

const WAIT_TEXT: Record<string, string> = {
  intake: "Waiting for documents",
  research: "Waits for plan approval",
  precedent: "Waiting for sources",
  opposing_counsel: "Waiting for sources",
  citation_firewall: "Waiting for sources",
  memo: "Waiting for verified sources",
};

/** Merge a streamed event into the step list (replace same agent+started_at, keep seq order). */
export function mergeStep(steps: TraceEvent[], ev: TraceEvent): TraceEvent[] {
  if (steps.some((s) => s.seq === ev.seq && s.agent === ev.agent && s.status === ev.status)) return steps;
  return [...steps, ev].sort((a, b) => a.seq - b.seq);
}

export function buildTrace(steps: TraceEvent[]): TraceRow[] {
  // instance = (agent, started_at); the latest event of an instance carries its state
  const inst = new Map<string, TraceEvent[]>();
  for (const s of steps) {
    const k = `${s.agent}|${s.started_at ?? s.seq}`;
    inst.set(k, [...(inst.get(k) ?? []), s]);
  }
  const byAgent = new Map<AgentName, TraceEvent[]>();
  for (const evs of inst.values()) {
    const last = evs.reduce((a, b) => (b.seq >= a.seq ? b : a));
    byAgent.set(last.agent, [...(byAgent.get(last.agent) ?? []), last]);
  }
  const rows: TraceRow[] = [];
  for (const { agent, label } of ORDER) {
    const list = (byAgent.get(agent) ?? []).sort((a, b) => a.seq - b.seq);
    if (agent === "citation_firewall") {
      const first = list.find((e) => e.data?.phase !== "memo") ?? null;
      const memo = list.filter((e) => e.data?.phase === "memo" || (first && e !== first)).pop() ?? null;
      rows.push(toRow(agent, label, first, 1, first ? list.filter((e) => e !== memo).length : 0));
      if (memo) rows.push(toRow(agent, "Citation Firewall (memo)", memo, 1, 1, "memo"));
      continue;
    }
    rows.push(toRow(agent, label, list[list.length - 1] ?? null, list.length, list.length));
  }
  // memo agent waits until firewall; mark placeholders
  return rows;
}

function toRow(agent: AgentName, label: string, e: TraceEvent | null, _n: number, runs: number, tag = ""): TraceRow {
  if (!e) {
    return { id: `${agent}${tag}`, agent, label, status: "waiting", summary: WAIT_TEXT[agent] ?? "Waiting", runs: 0, placeholder: true };
  }
  return {
    id: `${agent}${tag}`, agent, label, status: e.status, summary: e.summary, duration_ms: e.duration_ms,
    started_at: e.started_at, runs, placeholder: false,
  };
}
