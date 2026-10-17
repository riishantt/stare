import type { TraceRow } from "../lib/trace";
import { fmtSecs } from "../util";

const STATUS_TEXT: Record<string, string> = { waiting: "waiting", running: "running", done: "done", error: "error", skipped: "skipped" };

export default function AgentTraceCard({ row, now }: { row: TraceRow; now: number }) {
  let timing = "";
  if (row.status === "running" && row.started_at) timing = `running ${Math.max(0, (now - new Date(row.started_at).getTime()) / 1000).toFixed(0)} s`;
  else if (row.status === "done" || row.status === "error") timing = `${STATUS_TEXT[row.status]} ${fmtSecs(row.duration_ms)}`.trim();
  else timing = STATUS_TEXT[row.status];
  return (
    <li className={`card flex gap-3 p-3 ${row.status === "error" ? "!border-red-300" : ""} ${row.status === "waiting" ? "opacity-70" : ""}`}>
      <span className={`dot dot-${row.status} mt-1.5`} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-2">
          <span className="font-semibold text-navy">{row.label}</span>
          <span className={`text-xs font-semibold ${row.status === "error" ? "text-bad" : row.status === "running" ? "text-amber-dark" : "text-muted"}`}>
            {timing}
          </span>
        </div>
        <p className="mt-0.5 break-words text-[13px] text-ink/80">{row.summary || "-"}</p>
        {row.runs > 1 && row.agent !== "citation_firewall" && (
          <span className="chip chip-warn mt-1" title="The Research Agent was sent back to search again because coverage was thin">
            ↻ loop: ran {row.runs} times
          </span>
        )}
      </div>
    </li>
  );
}
