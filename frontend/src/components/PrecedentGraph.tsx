import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { GraphEdge, GraphNode, GraphOut } from "../api/types";
import { errMsg } from "../util";

const W = 900;
const H = 560;
const FILL: Record<string, string> = { verified: "#16a34a", warning: "#f5a623", blocked: "#dc2626", unresolved: "#9aa5b6" };
const LABEL: Record<string, string> = { verified: "Verified", warning: "Warning", blocked: "Blocked", unresolved: "Unresolved" };

interface P { x: number; y: number; vx: number; vy: number }

/** Small deterministic force layout: repulsion + spring edges + centre gravity. */
function layout(nodes: GraphNode[], edges: GraphEdge[]): Map<string, P> {
  const pos = new Map<string, P>();
  nodes.forEach((n, i) => {
    const a = (2 * Math.PI * i) / Math.max(1, nodes.length);
    pos.set(n.id, { x: W / 2 + Math.cos(a) * 200, y: H / 2 + Math.sin(a) * 150, vx: 0, vy: 0 });
  });
  const ids = nodes.map((n) => n.id);
  for (let it = 0; it < 320; it++) {
    const cool = 1 - it / 320;
    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const a = pos.get(ids[i])!, b = pos.get(ids[j])!;
        let dx = a.x - b.x, dy = a.y - b.y;
        let d2 = dx * dx + dy * dy;
        if (d2 < 1) { dx = Math.random() - 0.5; dy = Math.random() - 0.5; d2 = 1; }
        const d = Math.sqrt(d2);
        const f = 5200 / d2;
        a.vx += (dx / d) * f; a.vy += (dy / d) * f;
        b.vx -= (dx / d) * f; b.vy -= (dy / d) * f;
      }
    }
    for (const e of edges) {
      const a = pos.get(e.source), b = pos.get(e.target);
      if (!a || !b) continue;
      const dx = b.x - a.x, dy = b.y - a.y;
      const d = Math.sqrt(dx * dx + dy * dy) || 1;
      const f = (d - 150) * 0.03;
      a.vx += (dx / d) * f; a.vy += (dy / d) * f;
      b.vx -= (dx / d) * f; b.vy -= (dy / d) * f;
    }
    for (const id of ids) {
      const p = pos.get(id)!;
      p.vx += (W / 2 - p.x) * 0.012; p.vy += (H / 2 - p.y) * 0.015;
      p.x += Math.max(-30, Math.min(30, p.vx)) * cool; p.y += Math.max(-30, Math.min(30, p.vy)) * cool;
      p.vx *= 0.6; p.vy *= 0.6;
      p.x = Math.max(60, Math.min(W - 60, p.x)); p.y = Math.max(40, Math.min(H - 40, p.y));
    }
  }
  return pos;
}

function Shape({ n, cx, cy, active }: { n: GraphNode; cx: number; cy: number; active: boolean }) {
  const fill = FILL[n.check_status ?? "unresolved"] ?? FILL.unresolved;
  const common = { fill, stroke: "#0b1f3a", strokeWidth: n.status === "binding" ? 4 : 2, strokeDasharray: n.status === "persuasive" ? "4 3" : undefined } as const;
  const r = 15;
  if (n.adverse) return <polygon points={`${cx},${cy - r - 4} ${cx + r + 4},${cy} ${cx},${cy + r + 4} ${cx - r - 4},${cy}`} {...common} stroke={active ? "#f5a623" : "#b42318"} strokeWidth={active ? 4 : 3} />;
  if (n.status === "flagged") return <rect x={cx - r} y={cy - r} width={2 * r} height={2 * r} rx={4} {...common} />;
  return <circle cx={cx} cy={cy} r={r} {...common} stroke={active ? "#f5a623" : "#0b1f3a"} />;
}

export default function PrecedentGraph({ runId, refreshKey, onSelect }: { runId: number; refreshKey: string; onSelect: (id: string, node: GraphNode) => void }) {
  const [g, setG] = useState<GraphOut | null>(null);
  const [err, setErr] = useState("");
  const [hover, setHover] = useState<GraphNode | null>(null);

  useEffect(() => { api.graph(runId).then((x) => { setG(x); setErr(""); }).catch((e) => setErr(errMsg(e))); }, [runId, refreshKey]);
  const pos = useMemo(() => (g ? layout(g.nodes, g.edges) : new Map<string, P>()), [g]);

  if (err) return <div className="alert alert-bad" role="alert">{err}</div>;
  if (!g) return <p className="text-muted" role="status">Loading graph...</p>;
  if (g.nodes.length === 0) return <div className="card card-b text-muted">The precedent graph appears once the Precedent Agent has mapped how the retrieved cases cite each other.</div>;
  const hp = hover ? pos.get(hover.id) : null;

  return (
    <section className="card min-w-0" aria-label="Precedent graph">
      <div className="card-h flex-wrap">
        <h2>Precedent graph</h2>
        <ul className="flex flex-wrap items-center gap-3 text-xs font-normal text-muted" aria-label="Legend">
          {Object.entries(LABEL).map(([k, v]) => <li key={k} className="flex items-center gap-1"><span className="dot" style={{ background: FILL[k] }} />{v}</li>)}
          <li><b className="text-navy">Thick ring</b> binding</li>
          <li><b className="text-navy">Dashed ring</b> persuasive</li>
          <li><b className="text-navy">◆ Diamond</b> adverse</li>
          <li><b className="text-navy">■ Square</b> flagged</li>
        </ul>
      </div>
      <div className="relative overflow-auto p-2">
        <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full min-w-[640px]" role="group" aria-label="Directed graph of how cited cases treat each other">
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#5b6678" /></marker>
          </defs>
          {g.edges.map((e, i) => {
            const a = pos.get(e.source), b = pos.get(e.target);
            if (!a || !b) return null;
            const dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) || 1;
            const x2 = b.x - (dx / d) * 22, y2 = b.y - (dy / d) * 22;
            return (
              <g key={i}>
                <line x1={a.x} y1={a.y} x2={x2} y2={y2} stroke="#8a95a8" strokeWidth={1.5} markerEnd="url(#arrow)" />
                {e.treatment && (
                  <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 4} textAnchor="middle" fontSize="10.5" fill="#33405a" stroke="#fff" strokeWidth="3" paintOrder="stroke">{e.treatment}</text>
                )}
              </g>
            );
          })}
          {g.nodes.map((n) => {
            const p = pos.get(n.id)!;
            return (
              <g key={n.id} tabIndex={0} role="button" aria-label={`${n.label}, ${n.citation}, ${LABEL[n.check_status ?? "unresolved"]}${n.adverse ? ", adverse" : ""}${n.status ? `, ${n.status}` : ""}`}
                className="cursor-pointer outline-none focus-visible:[&>*:first-child]:stroke-[#f5a623]"
                onMouseEnter={() => setHover(n)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(n)} onBlur={() => setHover(null)}
                onClick={() => onSelect(n.id, n)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(n.id, n); } }}>
                <Shape n={n} cx={p.x} cy={p.y} active={hover?.id === n.id} />
                <text x={p.x} y={p.y + 34} textAnchor="middle" fontSize="11" fontStyle="italic" fill="#1b2536" stroke="#fff" strokeWidth="3" paintOrder="stroke">
                  {n.label.length > 28 ? n.label.slice(0, 27) + "…" : n.label}
                </text>
              </g>
            );
          })}
        </svg>
        {hover && hp && (
          <div className="pointer-events-none absolute z-10 max-w-xs rounded-md bg-navy px-3 py-2 text-xs text-white shadow-lg"
            style={{ left: `${(hp.x / W) * 100}%`, top: `${(hp.y / H) * 100}%`, transform: "translate(-50%, -135%)" }} role="tooltip">
            <p className="font-semibold italic">{hover.label}</p>
            <p>{hover.citation}</p>
            <p className="text-slate-300">{[hover.court, hover.year].filter(Boolean).join(", ")}</p>
            <p>{LABEL[hover.check_status ?? "unresolved"]}{hover.status ? ` · ${hover.status}` : ""}{hover.adverse ? " · adverse" : ""}</p>
            <p className="text-amber">Click to jump to its source card</p>
          </div>
        )}
      </div>
    </section>
  );
}
