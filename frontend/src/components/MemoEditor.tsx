import { Fragment, useEffect, useState } from "react";
import { api, ApiError, downloadBlob } from "../api/client";
import type { Memo, RunOut } from "../api/types";
import { findSource, scrollToSource, type SourceItem } from "../lib/sources";
import { errMsg, fmtTime } from "../util";
import { CheckBadge } from "./StatusBadge";

const SECTIONS: { key: "question_presented" | "issue" | "rule" | "application" | "conclusion"; title: string }[] = [
  { key: "question_presented", title: "Question Presented" },
  { key: "issue", title: "Issue" },
  { key: "rule", title: "Rule" },
  { key: "application", title: "Application" },
  { key: "conclusion", title: "Conclusion" },
];

/** Minimal inline markdown used by the memo drafter: **bold** and *italic*. */
function Inline({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\*\*[^*]+\*\*|\*[^*\n]+\*)/g).map((part, i) => {
        if (/^\*\*[^*]+\*\*$/.test(part)) return <strong key={i}>{part.slice(2, -2)}</strong>;
        if (/^\*[^*\n]+\*$/.test(part)) return <em key={i}>{part.slice(1, -1)}</em>;
        return <Fragment key={i}>{part}</Fragment>;
      })}
    </>
  );
}

function WithMarkers({ text, memo, items }: { text: string; memo: Memo; items: SourceItem[] }) {
  return (
    <>
      {text.split(/(\[\d+\])/g).map((part, i) => {
        const cit = /^\[\d+\]$/.test(part) ? memo.citations.find((c) => c.marker === part) : undefined;
        if (!cit) return <Inline key={i} text={part} />;
        const src = findSource(items, cit);
        return (
          <button key={i} type="button"
            className="mx-0.5 rounded bg-amber-bg px-1 font-sans text-[12px] font-bold text-amber-dark underline decoration-dotted hover:bg-amber hover:text-navy"
            title={`${cit.case_name || cit.citation} - ${cit.citation}. Click to show the source card.`}
            onClick={() => src && scrollToSource(src.key)} disabled={!src}>
            {part}
          </button>
        );
      })}
    </>
  );
}

export default function MemoEditor({ run, memo, items, isAttorney, onView, onChanged }: {
  run: RunOut; memo: Memo; items: SourceItem[]; isAttorney: boolean; onView: (i: SourceItem) => void; onChanged: () => void;
}) {
  const awaiting = run.status === "awaiting_memo_approval";
  const canEdit = awaiting && isAttorney;
  const [draft, setDraft] = useState<Memo>(memo);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState<ApiError | string | null>(null);
  const [asking, setAsking] = useState(false);
  const [instr, setInstr] = useState("");

  useEffect(() => { if (!editing) setDraft(memo); }, [memo, editing]);
  const dirty = JSON.stringify(draft) !== JSON.stringify(memo);
  const approved = run.status === "approved" || run.status === "exported";

  async function approve() {
    setBusy("approve");
    setErr(null);
    try { await api.approveMemo(run.id, dirty ? draft : undefined); setEditing(false); onChanged(); }
    catch (e) { setErr(e instanceof ApiError ? e : errMsg(e)); } finally { setBusy(""); }
  }
  async function changes() {
    setBusy("changes");
    setErr(null);
    try { await api.requestChanges(run.id, instr.trim()); setAsking(false); setInstr(""); onChanged(); }
    catch (e) { setErr(e instanceof ApiError ? e : errMsg(e)); } finally { setBusy(""); }
  }
  async function exportDocx() {
    setBusy("export");
    setErr(null);
    try { downloadBlob(await api.exportDocx(run.id), `STARE-memo-run-${run.id}.docx`); onChanged(); }
    catch (e) { setErr(e instanceof ApiError ? e : errMsg(e)); } finally { setBusy(""); }
  }

  const exportReason = !isAttorney ? "Only an attorney can export the memo."
    : !approved ? "Export is disabled until an attorney approves the memo." : "";

  return (
    <div className="space-y-4">
      <section className="card" aria-label="Research memo">
        <div className="card-h flex-wrap">
          <h2>{memo.title || "Research memo"}</h2>
          <span className="flex items-center gap-2 text-xs font-normal text-muted">
            {run.memo_version != null && <span>Draft v{run.memo_version}</span>}
            <span>drafted by {memo.generated_by}</span>
            {approved && run.memo_approved_at && <span className="chip chip-ok">Approved {fmtTime(run.memo_approved_at)}</span>}
          </span>
        </div>
        <div className="card-b space-y-5">
          {SECTIONS.map((s) => (
            <div key={s.key}>
              <h3 className="mb-1 text-sm font-bold uppercase tracking-wide text-navy">{s.title}</h3>
              {editing ? (
                <textarea aria-label={s.title} className="input legal" rows={s.key === "application" || s.key === "rule" ? 10 : 4}
                  value={draft[s.key]} onChange={(e) => setDraft({ ...draft, [s.key]: e.target.value })} />
              ) : (
                <p className="legal whitespace-pre-wrap"><WithMarkers text={memo[s.key]} memo={memo} items={items} /></p>
              )}
            </div>
          ))}
          {editing && <p className="alert alert-info text-xs">Citation markers like [1] refer to the numbered references below. Any new or changed citation is re-checked by the Citation Firewall when you approve.</p>}
        </div>
        <div className="border-t border-line px-4 py-3">
          <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-navy">References</h3>
          {memo.citations.length === 0 ? <p className="text-muted">No citations in this memo.</p> : (
            <ol className="space-y-1.5">
              {memo.citations.map((c) => {
                const src = findSource(items, c);
                return (
                  <li key={c.marker} className="flex flex-wrap items-center gap-2 text-[13px]">
                    <span className="w-8 font-bold text-amber-dark">{c.marker}</span>
                    <CheckBadge status={c.status} />
                    <span className="min-w-0 flex-1"><i>{c.case_name}</i> <span className="font-mono text-xs text-muted">{c.citation}</span></span>
                    {src && <button className="btn btn-sm" onClick={() => scrollToSource(src.key)}>Show source</button>}
                    {src?.opinionId != null && <button className="btn btn-sm" onClick={() => onView(src)}>View opinion</button>}
                    {c.url && <a className="text-xs text-navy underline" href={c.url} target="_blank" rel="noreferrer">Link</a>}
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <section className="card" aria-label="Adverse authority report">
          <div className="card-h"><h2>Adverse Authority report</h2><span className="chip chip-bad">Opposing Counsel</span></div>
          <p className="card-b legal whitespace-pre-wrap">
            {memo.adverse_authority ? <WithMarkers text={memo.adverse_authority} memo={memo} items={items} /> : <span className="text-muted">No adverse authority was found.</span>}
          </p>
        </section>
        <div className="space-y-4">
          <section className="card" aria-label="Firewall warnings">
            <div className="card-h"><h2>Firewall warnings</h2><span className="chip chip-warn">{memo.warnings.length}</span></div>
            <div className="card-b">
              {memo.warnings.length === 0 ? <p className="text-muted">No warnings.</p> : (
                <ul className="space-y-1.5">{memo.warnings.map((w, i) => <li key={i} className="alert alert-warn text-[13px]"><strong>Warning: </strong>{w}</li>)}</ul>
              )}
            </div>
          </section>
          <section className="card" aria-label="Removed by the Citation Firewall">
            <div className="card-h"><h2>Removed by the Citation Firewall</h2><span className="chip chip-bad">{memo.removed_citations.length}</span></div>
            <div className="card-b">
              {memo.removed_citations.length === 0 ? <p className="text-muted">Nothing was removed.</p> : (
                <ul className="space-y-1.5">{memo.removed_citations.map((w, i) => <li key={i} className="alert alert-bad text-[13px]"><strong>Removed: </strong>{w}</li>)}</ul>
              )}
            </div>
          </section>
        </div>
      </div>

      {err && (
        <div className="alert alert-bad" role="alert">
          <p className="font-semibold">{typeof err === "string" ? err : err.message}</p>
          {typeof err !== "string" && err.problems.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-[13px]">{err.problems.map((p, i) => <li key={i}>{p}</li>)}</ul>
          )}
          {typeof err !== "string" && err.status === 422 && <p className="mt-1 text-xs">Edited citations must pass the Citation Firewall. Remove or correct them and try again.</p>}
        </div>
      )}

      <div className="card card-b flex flex-wrap items-center gap-2" role="group" aria-label="Memo actions">
        {canEdit && !editing && <button className="btn" onClick={() => setEditing(true)}>Edit memo</button>}
        {canEdit && editing && <button className="btn" onClick={() => { setDraft(memo); setEditing(false); }}>Discard edits</button>}
        {canEdit && <button className="btn" onClick={() => setAsking((a) => !a)} aria-expanded={asking}>Request changes</button>}
        {canEdit && <button className="btn btn-amber" disabled={busy !== ""} onClick={approve}>{busy === "approve" ? "Verifying and approving..." : dirty ? "Approve edited memo" : "Approve memo"}</button>}
        {!isAttorney && awaiting && <span className="text-muted">Read-only: waiting for attorney review.</span>}
        <span className="ml-auto" title={exportReason}>
          <button className="btn btn-primary" disabled={!!exportReason || busy !== ""} onClick={exportDocx} aria-describedby="export-why">
            {busy === "export" ? "Exporting..." : "Export DOCX"}
          </button>
        </span>
        {exportReason && <span id="export-why" className="w-full text-xs text-muted">{exportReason}</span>}
        {asking && canEdit && (
          <div className="mt-2 w-full space-y-2">
            <label className="label" htmlFor="chg">What should change?</label>
            <textarea id="chg" className="input" rows={3} value={instr} onChange={(e) => setInstr(e.target.value)} placeholder="e.g. Add Fifth Circuit authority on the but-for causation standard" />
            <button className="btn btn-primary btn-sm" disabled={!instr.trim() || busy !== ""} onClick={changes}>{busy === "changes" ? "Sending..." : "Send to Memo Agent"}</button>
          </div>
        )}
      </div>
      {memo.disclaimer && <p className="text-xs italic text-muted">{memo.disclaimer}</p>}
    </div>
  );
}
