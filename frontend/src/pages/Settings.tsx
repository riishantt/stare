import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { Health, SettingsOut } from "../api/types";
import { ErrorBox } from "../components/Spinner";
import { errMsg } from "../util";

function providerText(p: string): string {
  return p === "offline" || p === "offline-deterministic" ? "offline (deterministic, no API cost)" : p;
}

export default function Settings() {
  const [s, setS] = useState<SettingsOut | null>(null);
  const [h, setH] = useState<Health | null>(null);
  const [days, setDays] = useState(30);
  const [err, setErr] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.settings().then((x) => { setS(x); setDays(x.retention_days); }).catch((e) => setErr(errMsg(e)));
    api.health().then(setH).catch(() => {});
  }, []);

  async function save(e: FormEvent) {
    e.preventDefault();
    setErr("");
    setSaved(false);
    try { const x = await api.patchSettings({ retention_days: days }); setS(x); setSaved(true); } catch (x) { setErr(errMsg(x)); }
  }

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-xl font-bold text-navy">Settings</h1>
      {err && <ErrorBox message={err} />}
      <form onSubmit={save} className="card card-b space-y-4" aria-label="Settings">
        <div>
          <label className="label" htmlFor="ret">Data retention (days)</label>
          <input id="ret" type="number" min={1} max={3650} className="input !w-40" value={days} onChange={(e) => setDays(Number(e.target.value))} />
          <p className="mt-1 text-xs text-muted">Matters, documents and runs older than this are purged.</p>
        </div>
        <div>
          <span className="label">LLM provider (read-only)</span>
          <p className="rounded-md bg-paper px-3 py-2 font-medium">{s ? providerText(s.llm_provider) : "-"}</p>
          {s && s.model && <p className="mt-1 text-xs text-muted">Model: {s.model}{s.fast_model ? ` · fast model: ${s.fast_model}` : ""}</p>}
        </div>
        <div className="flex items-center gap-3">
          <button className="btn btn-primary" disabled={!s}>Save settings</button>
          {saved && <span className="chip chip-ok" role="status">Saved</span>}
        </div>
      </form>
      {h && (
        <section className="card card-b" aria-label="System status">
          <h2 className="mb-2 font-bold text-navy">System status</h2>
          <dl className="grid grid-cols-2 gap-y-1 text-[13px]">
            <dt className="text-muted">API</dt><dd>{h.status} (v{h.version})</dd>
            <dt className="text-muted">Opinions indexed</dt><dd>{h.corpus?.opinions ?? "-"}</dd>
            <dt className="text-muted">Statute sections</dt><dd>{h.corpus?.statutes ?? "-"}</dd>
            <dt className="text-muted">Search chunks</dt><dd>{h.corpus?.chunks ?? "-"}</dd>
          </dl>
        </section>
      )}
    </div>
  );
}
