import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { AuditRow } from "../api/types";
import { ErrorBox } from "../components/Spinner";
import { errMsg, fmtDate } from "../util";

export default function AuditLog() {
  const [rows, setRows] = useState<AuditRow[] | null>(null);
  const [action, setAction] = useState("");
  const [runId, setRunId] = useState("");
  const [err, setErr] = useState("");
  const [open, setOpen] = useState<number | null>(null);

  const load = useCallback(() => {
    setErr("");
    api.audit({ action: action.trim() || undefined, run_id: runId.trim() || undefined })
      .then((r) => setRows([...r].sort((a, b) => b.at.localeCompare(a.at))))
      .catch((e) => setErr(errMsg(e)));
  }, [action, runId]);
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const actions = Array.from(new Set((rows ?? []).map((r) => r.action))).sort();
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-navy">Audit log</h1>
      <form className="card card-b flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); load(); }}>
        <div>
          <label className="label" htmlFor="af-a">Action</label>
          <input id="af-a" list="actions" className="input !w-60" placeholder="e.g. plan.approved" value={action} onChange={(e) => setAction(e.target.value)} />
          <datalist id="actions">{actions.map((a) => <option key={a} value={a} />)}</datalist>
        </div>
        <div>
          <label className="label" htmlFor="af-r">Run id</label>
          <input id="af-r" className="input !w-28" inputMode="numeric" value={runId} onChange={(e) => setRunId(e.target.value.replace(/\D/g, ""))} />
        </div>
        <button className="btn btn-primary">Apply filters</button>
        <button type="button" className="btn" onClick={() => { setAction(""); setRunId(""); setTimeout(load, 0); }}>Reset</button>
      </form>
      {err && <ErrorBox message={err} />}
      <div className="card overflow-x-auto">
        <table className="w-full">
          <thead><tr><th className="th">Time</th><th className="th">User</th><th className="th">Action</th><th className="th">Entity</th><th className="th">Detail</th></tr></thead>
          <tbody>
            {rows?.map((r) => (
              <tr key={r.id}>
                <td className="td whitespace-nowrap text-muted">{fmtDate(r.at)}</td>
                <td className="td">{r.user_name ?? (r.user_id ? `user ${r.user_id}` : "system")}</td>
                <td className="td"><span className="chip chip-navy">{r.action}</span></td>
                <td className="td">{r.entity}{r.entity_id != null ? ` #${r.entity_id}` : ""}</td>
                <td className="td">
                  {Object.keys(r.detail).length ? (
                    <>
                      <button className="text-xs text-navy underline" aria-expanded={open === r.id} onClick={() => setOpen(open === r.id ? null : r.id)}>{open === r.id ? "hide" : "show"}</button>
                      {open === r.id && <pre className="mt-1 max-w-xl overflow-auto whitespace-pre-wrap rounded bg-paper p-2 text-xs">{JSON.stringify(r.detail, null, 2)}</pre>}
                    </>
                  ) : <span className="text-muted">-</span>}
                </td>
              </tr>
            ))}
            {rows && rows.length === 0 && <tr><td className="td text-muted" colSpan={5}>No audit entries match.</td></tr>}
          </tbody>
        </table>
        {!rows && !err && <p className="p-4 text-muted" role="status">Loading...</p>}
      </div>
    </div>
  );
}
