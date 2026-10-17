import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Court, MatterDetail, RunOut, TraceEvent } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useRunEvents } from "../hooks/useRunEvents";
import { buildSources, findSource, scrollToSource, type SourceItem } from "../lib/sources";
import { buildTrace, mergeStep } from "../lib/trace";
import AgentTraceCard from "../components/AgentTraceCard";
import CaseFileCard from "../components/CaseFileCard";
import MemoEditor from "../components/MemoEditor";
import OpinionDrawer from "../components/OpinionDrawer";
import PlanEditor from "../components/PlanEditor";
import PrecedentGraph from "../components/PrecedentGraph";
import SourcesPanel from "../components/SourcesPanel";
import { RunStatusPill, runStatusInfo } from "../components/StatusBadge";
import { ErrorBox, Loading } from "../components/Spinner";
import { claimLabel, errMsg } from "../util";

type View = "workspace" | "memo" | "graph";
const TARGET_S = 90;

export default function RunWorkspace() {
  const id = Number(useParams().id);
  const { isRole } = useAuth();
  const isAttorney = isRole("attorney");
  const canEditCase = isRole("attorney", "paralegal");

  const [run, setRun] = useState<RunOut | null>(null);
  const [matter, setMatter] = useState<MatterDetail | null>(null);
  const [courts, setCourts] = useState<Court[]>([]);
  const [err, setErr] = useState("");
  const [view, setView] = useState<View>("workspace");
  const [drawer, setDrawer] = useState<{ opinionId: number; quote: string } | null>(null);
  const [now, setNow] = useState(Date.now());
  const autoSwitched = useRef(false);

  const refresh = useCallback(async () => {
    try { setRun(await api.run(id)); setErr(""); } catch (e) { setErr(errMsg(e)); }
  }, [id]);

  useEffect(() => { setRun(null); autoSwitched.current = false; refresh(); }, [refresh]);
  useEffect(() => { api.courts().then(setCourts).catch(() => {}); }, []);
  useEffect(() => {
    if (run?.case_id != null && matter?.id !== run.case_id) api.matter(run.case_id).then(setMatter).catch(() => {});
  }, [run?.case_id, matter?.id]);

  useRunEvents(id, {
    onTrace: (e: TraceEvent) => setRun((r) => (r ? { ...r, steps: mergeStep(r.steps, e) } : r)),
    onStatus: (s) => { setRun((r) => (r ? { ...r, status: s } : r)); refresh(); },
    onOpen: refresh,
  });

  const busy = run ? runStatusInfo(run.status).busy : false;
  const anyRunning = !!run?.steps.length && buildTrace(run.steps).some((r) => r.status === "running");
  useEffect(() => {
    if (!busy && !anyRunning) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [busy, anyRunning]);
  // safety net if the event stream drops
  useEffect(() => {
    if (!busy) return;
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [busy, refresh]);

  const hasMemo = !!run?.memo && ["awaiting_memo_approval", "approved", "exported"].includes(run.status);
  useEffect(() => {
    if (hasMemo && !autoSwitched.current) { autoSwitched.current = true; setView("memo"); }
    if (!hasMemo && view === "memo") setView("workspace");
  }, [hasMemo, view]);

  const items = useMemo(() => buildSources(run), [run]);
  const trace = useMemo(() => buildTrace(run?.steps ?? []), [run?.steps]);
  const openOpinion = useCallback((i: SourceItem) => { if (i.opinionId != null) setDrawer({ opinionId: i.opinionId, quote: i.quote }); }, []);

  if (!run) return err ? <ErrorBox message={err} /> : <Loading text="Loading research run..." />;

  const rec = run.case_record;
  const runNo = matter ? [...matter.runs].sort((a, b) => a.id - b.id).findIndex((r) => r.id === run.id) + 1 : undefined;
  const plaintiff = rec?.parties.find((p) => p.role === "plaintiff")?.name ?? "[PLAINTIFF]";
  const defendant = rec?.parties.find((p) => p.role === "defendant")?.name;

  // elapsed / target (counted from plan approval)
  const approvedMs = run.plan_approved_at ? new Date(run.plan_approved_at).getTime() : null;
  const finished = ["awaiting_memo_approval", "approved", "exported", "failed", "cancelled"].includes(run.status);
  let elapsed = 0;
  if (approvedMs) {
    if (finished && run.latency_ms != null) elapsed = run.latency_ms / 1000;
    else if (finished) {
      const lastEnd = Math.max(0, ...run.steps.map((s) => (s.ended_at ? new Date(s.ended_at).getTime() : 0)));
      elapsed = Math.max(0, (lastEnd - approvedMs) / 1000);
    } else elapsed = Math.max(0, (now - approvedMs) / 1000);
  }
  const pct = Math.min(100, (elapsed / TARGET_S) * 100);
  const loops = trace.find((t) => t.agent === "research")?.runs ?? 0;
  const awaitingPlan = run.status === "awaiting_plan_approval";

  const tabs: [View, string, boolean][] = [["workspace", "Research workspace", true], ["memo", "Memo", hasMemo], ["graph", "Precedent graph", true]];
  const sources = <SourcesPanel items={items} onView={openOpinion} />;

  return (
    <div className="space-y-4">
      {/* header strip */}
      <div className="card card-b flex flex-wrap items-center gap-x-6 gap-y-2">
        <div className="min-w-0">
          <Link to={`/matters/${run.case_id}`} className="font-mono text-xs text-muted underline">{matter?.matter_number ?? `Matter ${run.case_id}`}</Link>
          <h1 className="truncate text-lg font-bold text-navy">{matter?.title ?? "Research run"}</h1>
        </div>
        <div className="text-[13px]">
          <span className="label !mb-0">Parties</span>
          <span className="ph">{plaintiff}</span> <span className="text-muted">v.</span> {defendant ?? "-"}
        </div>
        <div className="text-[13px]">
          <span className="label !mb-0">Court</span>
          {rec?.court_name ?? "Not identified"}{rec?.circuit ? ` (Circuit ${rec.circuit})` : ""}
        </div>
        <div className="text-[13px]">
          <span className="label !mb-0">Claims</span>
          <span className="flex flex-wrap gap-1">{rec?.claims.length ? rec.claims.map((c, i) => <span key={i} className="chip chip-navy">{claimLabel(c)}</span>) : "-"}</span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <RunStatusPill status={run.status} runNo={runNo || undefined} />
          {isAttorney && (busy || awaitingPlan || run.status === "awaiting_memo_approval") && (
            <button className="btn btn-sm btn-danger" onClick={async () => { if (confirm("Cancel this run?")) { try { await api.cancelRun(id); refresh(); } catch (e) { setErr(errMsg(e)); } } }}>Cancel run</button>
          )}
        </div>
      </div>
      {err && <ErrorBox message={err} />}
      {run.status === "failed" && <div className="alert alert-bad" role="alert"><strong>Run failed.</strong> {run.error ?? "An unexpected error occurred."}</div>}

      {/* view tabs */}
      <div role="tablist" aria-label="Workspace views" className="flex gap-1 border-b border-line">
        {tabs.filter((t) => t[2]).map(([k, label]) => (
          <button key={k} role="tab" aria-selected={view === k} onClick={() => setView(k)}
            className={`-mb-px rounded-t-md border-b-2 px-4 py-2 font-semibold ${view === k ? "border-amber text-navy" : "border-transparent text-muted hover:text-navy"}`}>
            {label}
          </button>
        ))}
      </div>

      {view === "workspace" && (
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] xl:grid-cols-[minmax(0,330px)_minmax(0,1fr)_minmax(0,400px)]">
          <div className="space-y-4">
            <CaseFileCard runId={id} record={rec} courts={courts} canEdit={canEditCase && awaitingPlan} onSaved={refresh} />
            <PlanEditor runId={id} plan={run.plan} awaiting={awaitingPlan} isAttorney={isAttorney} onApproved={refresh} />
          </div>
          <section className="space-y-3" aria-label="Live agent trace">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-navy">Live agent trace</h2>
              {run.llm_provider && <span className="chip chip-grey" title="Language model provider">{run.llm_provider}</span>}
            </div>
            <div className="card card-b !py-2.5">
              <div className="mb-1 flex justify-between text-xs font-semibold">
                <span>{approvedMs ? `elapsed ${Math.round(elapsed)} s / target ${TARGET_S} s` : `target ${TARGET_S} s after plan approval`}</span>
                <span className={elapsed > TARGET_S ? "text-bad" : "text-muted"}>{elapsed > TARGET_S ? "over target" : approvedMs ? "within target" : ""}</span>
              </div>
              <div className="h-2.5 overflow-hidden rounded-full bg-slate-200" role="progressbar" aria-valuemin={0} aria-valuemax={TARGET_S} aria-valuenow={Math.round(Math.min(elapsed, TARGET_S))} aria-label="Elapsed time against the 90 second target">
                <div className={`h-full rounded-full transition-all ${elapsed > TARGET_S ? "bg-bad" : "bg-amber"}`} style={{ width: `${pct}%` }} />
              </div>
              {loops > 1 && <p className="mt-2 text-xs font-semibold text-amber-dark">↻ Loop: the Research Agent searched {loops} times because coverage was thin.</p>}
            </div>
            <ol className="space-y-2" aria-live="polite" aria-label="Agent progress">
              {trace.map((r) => <AgentTraceCard key={r.id} row={r} now={now} />)}
            </ol>
            {run.cost_usd > 0 && <p className="text-xs text-muted">LLM cost so far: ${run.cost_usd.toFixed(3)}</p>}
          </section>
          <div className="lg:col-span-2 xl:col-span-1">{sources}</div>
        </div>
      )}

      {view === "memo" && run.memo && (
        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,400px)]">
          <MemoEditor run={run} memo={run.memo} items={items} isAttorney={isAttorney} onView={openOpinion} onChanged={refresh} />
          <div className="xl:sticky xl:top-3">{sources}</div>
        </div>
      )}

      {view === "graph" && (
        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,400px)]">
          <PrecedentGraph runId={id} refreshKey={`${run.status}:${run.authorities.length}`}
            onSelect={(nid, node) => { const s = findSource(items, { authority_key: nid, citation: node.citation }); if (s) scrollToSource(s.key); }} />
          {sources}
        </div>
      )}

      {drawer && <OpinionDrawer opinionId={drawer.opinionId} quote={drawer.quote} onClose={() => setDrawer(null)} />}
    </div>
  );
}
