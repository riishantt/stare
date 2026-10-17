import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { DocumentOut, MatterDetail } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { RunStatusPill } from "../components/StatusBadge";
import { ErrorBox, Loading } from "../components/Spinner";
import { errMsg, fmtDate, splitPlaceholders } from "../util";

function Redacted({ text }: { text: string }) {
  return (
    <div className="legal max-h-80 overflow-auto whitespace-pre-wrap rounded-md border border-line bg-paper p-3" tabIndex={0} aria-label="Redacted document text">
      {splitPlaceholders(text).map((p, i) => (p.ph ? <mark key={i} className="ph">{p.t}</mark> : <span key={i}>{p.t}</span>))}
    </div>
  );
}

function DocCard({ doc, canEdit, onSaved }: { doc: DocumentOut; canEdit: boolean; onSaved: (d: DocumentOut) => void }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(doc.redacted_text);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  async function save() {
    setBusy(true);
    setErr("");
    try {
      const d = await api.patchDocument(doc.id, text);
      onSaved(d);
      setEditing(false);
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  }
  return (
    <article className="card">
      <div className="card-h flex-wrap">
        <span>{doc.file_name}</span>
        <span className="flex flex-wrap items-center gap-1.5 text-xs font-normal">
          <span className="chip chip-navy">{doc.page_count} page{doc.page_count === 1 ? "" : "s"}</span>
          <span className="chip chip-warn">Personal details redacted: {doc.redaction_count}</span>
          {doc.ocr_used && <span className="chip chip-grey" title="Text was recognised from scanned pages and may contain errors">OCR used</span>}
          <span className="chip chip-grey">{doc.redaction_engine}</span>
        </span>
      </div>
      <div className="card-b space-y-3">
        {editing ? (
          <>
            <label className="label" htmlFor={`ed${doc.id}`}>Edit redactions (keep placeholders such as [PERSON_1])</label>
            <textarea id={`ed${doc.id}`} className="input legal h-72" value={text} onChange={(e) => setText(e.target.value)} />
            {err && <ErrorBox message={err} />}
            <div className="flex gap-2">
              <button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? "Saving..." : "Save redactions"}</button>
              <button className="btn" onClick={() => { setText(doc.redacted_text); setEditing(false); }}>Cancel</button>
            </div>
          </>
        ) : (
          <>
            <Redacted text={doc.redacted_text} />
            <div className="flex flex-wrap items-center gap-2">
              {canEdit && <button className="btn btn-sm" onClick={() => { setText(doc.redacted_text); setEditing(true); }}>Edit redactions</button>}
              <span className="text-xs text-muted">Only this redacted text is ever sent to a language model or stored.</span>
            </div>
          </>
        )}
      </div>
    </article>
  );
}

export default function MatterPage() {
  const id = Number(useParams().id);
  const nav = useNavigate();
  const { isRole } = useAuth();
  const canEdit = isRole("attorney", "paralegal");
  const [m, setM] = useState<MatterDetail | null>(null);
  const [err, setErr] = useState("");
  const [uploading, setUploading] = useState<string[]>([]);
  const [drag, setDrag] = useState(false);
  const [starting, setStarting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => api.matter(id).then(setM).catch((e) => setErr(errMsg(e))), [id]);
  useEffect(() => { load(); }, [load]);

  async function upload(files: FileList | File[]) {
    setErr("");
    for (const f of Array.from(files)) {
      if (!/\.(pdf|txt|docx)$/i.test(f.name)) { setErr(`${f.name}: only PDF, TXT and DOCX files are supported.`); continue; }
      setUploading((u) => [...u, f.name]);
      try { await api.uploadDocument(id, f); await load(); } catch (e) { setErr(`${f.name}: ${errMsg(e)}`); }
      setUploading((u) => u.filter((n) => n !== f.name));
    }
  }

  async function start() {
    setStarting(true);
    setErr("");
    try { const r = await api.startRun(id); nav(`/runs/${r.id}`); } catch (e) { setErr(errMsg(e)); setStarting(false); }
  }

  if (!m) return err ? <ErrorBox message={err} /> : <Loading />;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/" className="text-xs text-muted underline">Matters</Link>
          <h1 className="text-xl font-bold text-navy">{m.title}</h1>
          <p className="text-muted"><span className="font-mono">{m.matter_number}</span> · {m.court_name ?? "court not set"} · created {fmtDate(m.created_at)}</p>
          {m.notes && <p className="mt-1 max-w-3xl">{m.notes}</p>}
        </div>
        {canEdit && (
          <button className="btn btn-amber !px-5 !py-2" onClick={start} disabled={starting || m.documents.length === 0}
            title={m.documents.length === 0 ? "Upload at least one document first" : "Read the documents, then propose a research plan"}>
            {starting ? "Starting..." : "Start research run"}
          </button>
        )}
      </div>
      {err && <ErrorBox message={err} />}

      <div className="grid gap-5 lg:grid-cols-[1fr_340px]">
        <section className="space-y-4" aria-label="Documents">
          <h2 className="text-lg font-bold text-navy">Documents</h2>
          {canEdit && (
            <div
              onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
              onDragLeave={() => setDrag(false)}
              onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files); }}
              className={`rounded-xl border-2 border-dashed p-8 text-center transition-colors ${drag ? "border-amber bg-amber-bg" : "border-slate-300 bg-white"}`}
            >
              <p className="font-semibold text-navy">Drag and drop a complaint, EEOC charge or termination letter</p>
              <p className="text-xs text-muted">PDF, TXT or DOCX. Personal details are redacted automatically before anything is stored.</p>
              <button className="btn mt-3" onClick={() => fileRef.current?.click()}>Choose files</button>
              <input ref={fileRef} type="file" multiple accept=".pdf,.txt,.docx" className="sr-only" aria-label="Upload documents"
                onChange={(e) => { if (e.target.files) upload(e.target.files); e.target.value = ""; }} />
              {uploading.map((n) => <p key={n} className="mt-2 text-sm text-amber-dark" role="status">Uploading and redacting {n}...</p>)}
            </div>
          )}
          {m.documents.length === 0 && <p className="text-muted">No documents yet.</p>}
          {m.documents.map((d) => (
            <DocCard key={d.id} doc={d} canEdit={canEdit} onSaved={(nd) => setM((x) => x && { ...x, documents: x.documents.map((o) => (o.id === nd.id ? nd : o)) })} />
          ))}
        </section>

        <aside aria-label="Runs">
          <h2 className="mb-3 text-lg font-bold text-navy">Research runs</h2>
          <div className="card">
            {m.runs.length === 0 ? <p className="card-b text-muted">No runs yet.</p> : (
              <ul>
                {[...m.runs].sort((a, b) => b.id - a.id).map((r, i, arr) => (
                  <li key={r.id} className="border-b border-line last:border-0">
                    <Link to={`/runs/${r.id}`} className="flex items-center justify-between gap-2 px-4 py-3 hover:bg-paper">
                      <span>
                        <span className="font-semibold text-navy">Run {arr.length - i}</span>
                        <span className="block text-xs text-muted">{fmtDate(r.created_at)} · {r.llm_provider}</span>
                      </span>
                      <RunStatusPill status={r.status} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
