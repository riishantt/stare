import { useState } from "react";
import { api } from "../api/client";
import type { CaseRecord, Court, Claim, Statute } from "../api/types";
import { STATUTE_LABEL, claimLabel, errMsg } from "../util";

const EMPTY: CaseRecord = { parties: [], claims: [], key_dates: [], procedural_posture: "", facts_summary: "", redaction_count: 0, client_side: "plaintiff" };

export default function CaseFileCard({ runId, record, courts, canEdit, onSaved }: {
  runId: number; record: CaseRecord | null; courts: Court[]; canEdit: boolean; onSaved: () => void;
}) {
  const rec = record ?? EMPTY;
  const [editing, setEditing] = useState(false);
  const [d, setD] = useState<CaseRecord>(rec);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function save() {
    setBusy(true);
    setErr("");
    try {
      await api.putCaseRecord(runId, d);
      setEditing(false);
      onSaved();
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  }
  const setClaim = (i: number, p: Partial<Claim>) => setD({ ...d, claims: d.claims.map((c, j) => (j === i ? { ...c, ...p } : c)) });

  const plaintiff = rec.parties.find((p) => p.role === "plaintiff");
  const defendant = rec.parties.find((p) => p.role === "defendant");

  return (
    <section className="card" aria-label="Case file">
      <div className="card-h">
        <h2>Case file</h2>
        {canEdit && !editing && <button className="btn btn-sm" onClick={() => { setD(rec); setEditing(true); }}>Edit</button>}
      </div>
      <div className="card-b space-y-3 text-[13px]">
        {!record && <p className="text-muted">The Intake Agent has not produced a case record yet.</p>}
        {record && !editing && (
          <dl className="space-y-2.5">
            <Row k="Parties">
              {plaintiff ? plaintiff.name : "-"} <span className="text-muted">v.</span> {defendant ? defendant.name : "-"}
              <span className="block text-xs text-muted">Client side: {rec.client_side}</span>
            </Row>
            <Row k="Court">{rec.court_name || "Not identified"}{rec.circuit ? <span className="text-muted"> (Circuit {rec.circuit})</span> : ""}</Row>
            <Row k="Claims">
              {rec.claims.length ? <span className="flex flex-wrap gap-1">{rec.claims.map((c, i) => <span key={i} className="chip chip-navy" title={c.description}>{claimLabel(c)}</span>)}</span> : "-"}
            </Row>
            <Row k="Key dates">
              {rec.key_dates.length ? <ul>{rec.key_dates.map((k, i) => <li key={i}>{k.label}: <span className="font-medium">{k.date}</span></li>)}</ul> : "-"}
            </Row>
            {rec.procedural_posture && <Row k="Posture">{rec.procedural_posture}</Row>}
            {rec.facts_summary && <Row k="Facts">{rec.facts_summary}</Row>}
            <div className="alert alert-warn !py-1.5 text-xs font-semibold">Personal details redacted: {rec.redaction_count}</div>
          </dl>
        )}
        {editing && (
          <div className="space-y-3">
            <div>
              <label className="label" htmlFor="cr-court">Court</label>
              <select id="cr-court" className="input" value={d.court_id ?? ""} onChange={(e) => {
                const c = courts.find((x) => x.id === e.target.value);
                setD({ ...d, court_id: c?.id ?? null, court_name: c?.name ?? null, circuit: c?.circuit ?? null });
              }}>
                <option value="">Not identified</option>
                {courts.map((c) => <option key={c.id} value={c.id}>{c.short_name} - {c.name}</option>)}
              </select>
            </div>
            <div>
              <span className="label">Client side</span>
              <select aria-label="Client side" className="input" value={d.client_side} onChange={(e) => setD({ ...d, client_side: e.target.value as "plaintiff" | "defendant" })}>
                <option value="plaintiff">Plaintiff (employee)</option><option value="defendant">Defendant (employer)</option>
              </select>
            </div>
            <fieldset>
              <legend className="label">Claims</legend>
              {d.claims.map((c, i) => (
                <div key={i} className="mb-2 flex gap-1.5">
                  <select aria-label="Statute" className="input !w-28" value={c.statute} onChange={(e) => setClaim(i, { statute: e.target.value as Statute })}>
                    {Object.entries(STATUTE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                  <input aria-label="Theory" className="input" value={c.theory} placeholder="retaliation" onChange={(e) => setClaim(i, { theory: e.target.value.replace(/\s+/g, "_").toLowerCase() })} />
                  <button className="btn btn-sm btn-danger" aria-label="Remove claim" onClick={() => setD({ ...d, claims: d.claims.filter((_, j) => j !== i) })}>✕</button>
                </div>
              ))}
              <button className="btn btn-sm" onClick={() => setD({ ...d, claims: [...d.claims, { statute: "title_vii", theory: "disparate_treatment", description: "" }] })}>+ Add claim</button>
            </fieldset>
            <fieldset>
              <legend className="label">Key dates</legend>
              {d.key_dates.map((k, i) => (
                <div key={i} className="mb-2 flex gap-1.5">
                  <input aria-label="Date label" className="input" value={k.label} onChange={(e) => setD({ ...d, key_dates: d.key_dates.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)) })} />
                  <input aria-label="Date" className="input !w-36" value={k.date} placeholder="2026-03-14" onChange={(e) => setD({ ...d, key_dates: d.key_dates.map((x, j) => (j === i ? { ...x, date: e.target.value } : x)) })} />
                  <button className="btn btn-sm btn-danger" aria-label="Remove date" onClick={() => setD({ ...d, key_dates: d.key_dates.filter((_, j) => j !== i) })}>✕</button>
                </div>
              ))}
              <button className="btn btn-sm" onClick={() => setD({ ...d, key_dates: [...d.key_dates, { label: "", date: "" }] })}>+ Add date</button>
            </fieldset>
            <div>
              <label className="label" htmlFor="cr-post">Procedural posture</label>
              <input id="cr-post" className="input" value={d.procedural_posture} onChange={(e) => setD({ ...d, procedural_posture: e.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor="cr-facts">Facts summary</label>
              <textarea id="cr-facts" className="input" rows={4} value={d.facts_summary} onChange={(e) => setD({ ...d, facts_summary: e.target.value })} />
            </div>
            {err && <div className="alert alert-bad" role="alert">{err}</div>}
            <div className="flex gap-2">
              <button className="btn btn-primary btn-sm" disabled={busy} onClick={save}>{busy ? "Saving..." : "Save case record"}</button>
              <button className="btn btn-sm" onClick={() => setEditing(false)}>Cancel</button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] font-bold uppercase tracking-wide text-muted">{k}</dt>
      <dd>{children}</dd>
    </div>
  );
}
