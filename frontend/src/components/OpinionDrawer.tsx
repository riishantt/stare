import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { OpinionOut } from "../api/types";
import { errMsg } from "../util";

function quoteRegex(q: string): RegExp | null {
  const t = q.trim().replace(/^["“”']+|["“”']+$/g, "").replace(/\.\.\.|…/g, " ").trim();
  if (t.length < 8) return null;
  const words = t.split(/\s+/).slice(0, 60);
  const esc = words.map((w) =>
    w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/["“”]/g, "[\"“”]").replace(/['’‘]/g, "['’‘]"));
  try { return new RegExp(esc.join("\\s+"), "i"); } catch { return null; }
}

export default function OpinionDrawer({ opinionId, quote, onClose }: { opinionId: number; quote: string; onClose: () => void }) {
  const [op, setOp] = useState<OpinionOut | null>(null);
  const [err, setErr] = useState("");
  const markRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setOp(null);
    setErr("");
    api.opinion(opinionId).then(setOp).catch((e) => setErr(errMsg(e)));
  }, [opinionId]);

  useEffect(() => {
    closeRef.current?.focus();
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const parts = useMemo(() => {
    if (!op) return null;
    const re = quote ? quoteRegex(quote) : null;
    const m = re ? re.exec(op.text) : null;
    if (!m) return { before: op.text, hit: "", after: "", found: false };
    return { before: op.text.slice(0, m.index), hit: m[0], after: op.text.slice(m.index + m[0].length), found: true };
  }, [op, quote]);

  useEffect(() => { markRef.current?.scrollIntoView({ block: "center" }); }, [parts]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label="Opinion text">
      <div className="absolute inset-0 bg-navy/40" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-2xl flex-col bg-white shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-line bg-navy px-5 py-3 text-white">
          <div>
            <h2 className="text-base font-bold">{op ? <i>{op.case_name}</i> : "Opinion"}</h2>
            {op && <p className="text-xs text-slate-300">{op.citation} · {op.court ?? ""} {op.date_filed ? `· ${op.date_filed}` : ""}</p>}
          </div>
          <button ref={closeRef} className="rounded border border-white/40 px-2 py-1 text-sm hover:bg-white/10" onClick={onClose}>Close</button>
        </div>
        <div className="flex-1 overflow-auto px-5 py-4">
          {err && <div className="alert alert-bad" role="alert">{err}</div>}
          {!op && !err && <p className="text-muted" role="status">Loading opinion...</p>}
          {op && parts && (
            <>
              {quote && (
                <p className={`alert mb-3 text-xs ${parts.found ? "alert-ok" : "alert-warn"}`}>
                  {parts.found ? "The quoted passage is highlighted below." : "The quoted passage could not be located verbatim in the opinion text."}
                </p>
              )}
              {op.url && <p className="mb-3 text-xs"><a className="text-navy underline" href={op.url} target="_blank" rel="noreferrer">Open source record</a></p>}
              <div className="legal whitespace-pre-wrap">
                {parts.before}
                {parts.found && <mark ref={markRef} className="hl">{parts.hit}</mark>}
                {parts.after}
              </div>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
