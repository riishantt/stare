import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { PlanItem, ResearchPlan } from "../api/types";
import { errMsg, fmtTime, STATUTE_LABEL } from "../util";

export default function PlanEditor({ runId, plan, awaiting, isAttorney, onApproved }: {
  runId: number; plan: ResearchPlan | null; awaiting: boolean; isAttorney: boolean; onApproved: () => void;
}) {
  const [draft, setDraft] = useState<ResearchPlan | null>(plan);
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  // keep local edits while awaiting approval, unless the server's plan itself changed (a saved case record
  // redrafts it); otherwise mirror server state
  const planKey = JSON.stringify(plan);
  const lastKey = useRef(planKey);
  useEffect(() => {
    const changed = lastKey.current !== planKey;
    lastKey.current = planKey;
    if (!awaiting || !draft || changed) setDraft(plan);
    /* eslint-disable-next-line */
  }, [planKey, awaiting]);

  if (!draft) {
    return (
      <section className="card" aria-label="Research plan">
        <div className="card-h"><h2>Research plan</h2></div>
        <p className="card-b text-muted">The plan appears after the Intake Agent has read the documents.</p>
      </section>
    );
  }
  const editable = awaiting && isAttorney;
  const setItem = (id: string, p: Partial<PlanItem>) => setDraft({ ...draft, items: draft.items.map((i) => (i.id === id ? { ...i, ...p } : i)) });
  const checkedN = draft.items.filter((i) => i.checked).length;

  async function approve() {
    if (!draft) return;
    setBusy(true);
    setErr("");
    const items = draft.items.map((i) => ({ ...i, elements: i.elements.map((e) => e.trim()).filter(Boolean) }));
    try { await api.approvePlan(runId, { ...draft, items }); onApproved(); } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  }

  return (
    <section className="card" aria-label="Research plan">
      <div className="card-h"><h2>Research plan</h2><span className="text-xs font-normal text-muted">{checkedN} of {draft.items.length} selected</span></div>
      <div className="card-b space-y-3 text-[13px]">
        <p><span className="label !mb-0">Question</span>{draft.question}</p>
        <ul className="space-y-1.5">
          {draft.items.map((it) => (
            <li key={it.id} className="rounded-md border border-line">
              <div className="flex items-start gap-2 p-2">
                <input id={`pi-${it.id}`} type="checkbox" className="mt-1 h-4 w-4 accent-[#0b1f3a]" checked={it.checked} disabled={!editable}
                  onChange={(e) => setItem(it.id, { checked: e.target.checked })} />
                <label htmlFor={`pi-${it.id}`} className="flex-1 cursor-pointer">
                  <span className="font-medium">{it.issue}</span>
                  {it.statute && <span className="chip chip-navy ml-1.5">{STATUTE_LABEL[it.statute] ?? it.statute}</span>}
                </label>
                <button className="btn btn-sm" aria-expanded={open === it.id} onClick={() => setOpen(open === it.id ? null : it.id)}>
                  {open === it.id ? "Hide" : "Details"}
                </button>
              </div>
              {open === it.id && (
                <div className="space-y-2 border-t border-line bg-paper p-2.5">
                  <div>
                    <label className="label" htmlFor={`el-${it.id}`}>Legal elements (one per line)</label>
                    <textarea id={`el-${it.id}`} className="input" rows={Math.max(3, it.elements.length + 1)} disabled={!editable}
                      value={it.elements.join("\n")} onChange={(e) => setItem(it.id, { elements: e.target.value.split("\n") })} />
                  </div>
                  <div>
                    <span className="label">Search queries</span>
                    {it.queries.length ? <ul className="list-disc pl-5 text-xs text-muted">{it.queries.map((q, i) => <li key={i}>{q}</li>)}</ul>
                      : <p className="text-xs text-muted">The Research Agent fills these in when it runs.</p>}
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
        <label className="flex items-center gap-2">
          <input type="checkbox" className="h-4 w-4 accent-[#0b1f3a]" disabled={!editable} checked={draft.include_adverse}
            onChange={(e) => setDraft({ ...draft, include_adverse: e.target.checked })} />
          Search for adverse authority (Opposing Counsel)
        </label>
        <div>
          <label className="label" htmlFor="plan-ins">Add instruction</label>
          <textarea id="plan-ins" className="input" rows={2} disabled={!editable} placeholder="e.g. Focus on Fifth Circuit cases after 2015"
            value={draft.instructions} onChange={(e) => setDraft({ ...draft, instructions: e.target.value })} />
        </div>
        {err && <div className="alert alert-bad" role="alert">{err}</div>}
        {awaiting ? (
          isAttorney ? (
            <button className="btn btn-amber w-full !py-2" disabled={busy || checkedN === 0} onClick={approve}>{busy ? "Approving..." : "Approve plan"}</button>
          ) : (
            <p className="alert alert-info text-center font-semibold">Waiting for attorney approval</p>
          )
        ) : draft.approved_at ? (
          <p className="alert alert-ok font-semibold">Plan approved by attorney, {fmtTime(draft.approved_at)}</p>
        ) : null}
      </div>
    </section>
  );
}
