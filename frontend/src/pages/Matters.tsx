import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Court, MatterSummary } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { RunStatusPill } from "../components/StatusBadge";
import { ErrorBox, Loading } from "../components/Spinner";
import { claimLabel, errMsg, fmtDate } from "../util";

function CourtSelect({ courts, value, onChange }: { courts: Court[]; value: string; onChange: (v: string) => void }) {
  const [q, setQ] = useState("");
  const list = useMemo(() => {
    const s = q.toLowerCase();
    return courts.filter((c) => !s || c.name.toLowerCase().includes(s) || c.short_name.toLowerCase().includes(s) || c.id.includes(s)).slice(0, 300);
  }, [courts, q]);
  return (
    <div className="space-y-1.5">
      <input className="input" placeholder="Search courts (e.g. N.D. Tex., Fifth Circuit)" aria-label="Search courts" value={q} onChange={(e) => setQ(e.target.value)} />
      <select className="input" aria-label="Court" value={value} onChange={(e) => onChange(e.target.value)} size={1}>
        <option value="">Court not yet known</option>
        {list.map((c) => (
          <option key={c.id} value={c.id}>{c.short_name} - {c.name}{c.circuit ? ` (Circuit ${c.circuit})` : ""}</option>
        ))}
      </select>
      <p className="text-xs text-muted">{list.length} of {courts.length} courts shown</p>
    </div>
  );
}

export default function Matters() {
  const { isRole } = useAuth();
  const nav = useNavigate();
  const [matters, setMatters] = useState<MatterSummary[] | null>(null);
  const [courts, setCourts] = useState<Court[]>([]);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [court, setCourt] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const canCreate = isRole("attorney", "paralegal");

  useEffect(() => {
    api.matters().then(setMatters).catch((e) => setErr(errMsg(e)));
    api.courts().then(setCourts).catch(() => {});
  }, []);

  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const m = await api.createMatter({ title: title.trim(), court_id: court || null, notes });
      nav(`/matters/${m.id}`);
    } catch (x) { setErr(errMsg(x)); setBusy(false); }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-navy">Matters</h1>
        {canCreate && <button className="btn btn-amber" onClick={() => setOpen((o) => !o)} aria-expanded={open}>+ New matter</button>}
      </div>
      {err && <ErrorBox message={err} />}
      {open && (
        <form onSubmit={create} className="card card-b grid gap-4 md:grid-cols-2" aria-label="New matter">
          <div className="space-y-3">
            <div>
              <label className="label" htmlFor="mt">Title</label>
              <input id="mt" className="input" required maxLength={300} placeholder="e.g. Retaliation claim - warehouse supervisor" value={title} onChange={(e) => setTitle(e.target.value)} />
              <p className="mt-1 text-xs text-muted">Do not enter client names; personal details are redacted from uploaded documents, not from titles.</p>
            </div>
            <div>
              <label className="label" htmlFor="nt">Notes</label>
              <textarea id="nt" className="input" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} />
            </div>
          </div>
          <div>
            <span className="label">Court</span>
            <CourtSelect courts={courts} value={court} onChange={setCourt} />
            <div className="mt-4 flex gap-2">
              <button className="btn btn-primary" disabled={busy || !title.trim()}>{busy ? "Creating..." : "Create matter"}</button>
              <button type="button" className="btn" onClick={() => setOpen(false)}>Cancel</button>
            </div>
          </div>
        </form>
      )}
      {!matters ? <Loading /> : matters.length === 0 ? (
        <div className="card card-b text-muted">No matters yet. {canCreate ? "Create one to upload a complaint or EEOC charge." : ""}</div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full">
            <thead><tr><th className="th">Matter</th><th className="th">Title</th><th className="th">Court</th><th className="th">Claims</th><th className="th">Docs</th><th className="th">Latest run</th><th className="th">Created</th></tr></thead>
            <tbody>
              {matters.map((m) => (
                <tr key={m.id} className="hover:bg-paper">
                  <td className="td font-mono text-xs"><Link className="font-semibold text-navy underline" to={`/matters/${m.id}`}>{m.matter_number}</Link></td>
                  <td className="td">{m.title}</td>
                  <td className="td">{m.court_name ?? <span className="text-muted">not set</span>}</td>
                  <td className="td"><div className="flex flex-wrap gap-1">{m.claims.map((c, i) => <span key={i} className="chip chip-navy">{claimLabel(c)}</span>)}</div></td>
                  <td className="td">{m.document_count}</td>
                  <td className="td">{m.last_run_status ? <RunStatusPill status={m.last_run_status} /> : <span className="text-muted">none</span>}</td>
                  <td className="td text-muted">{fmtDate(m.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
