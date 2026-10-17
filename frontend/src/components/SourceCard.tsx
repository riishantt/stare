import { useState } from "react";
import type { GateOutcome } from "../api/types";
import type { SourceItem } from "../lib/sources";
import { CheckBadge } from "./StatusBadge";

const OUT: Record<GateOutcome, { t: string; c: string }> = {
  pass: { t: "PASS", c: "chip-ok" },
  warn: { t: "WARN", c: "chip-warn" },
  fail: { t: "FAIL", c: "chip-bad" },
  skip: { t: "SKIPPED", c: "chip-grey" },
  unresolved: { t: "UNRESOLVED", c: "chip-grey" },
};
const GATE_NAME = ["", "Citation extracted", "Case exists", "Quote matches", "Still good law"];

const RANK_CLS = { binding: "chip-navy", persuasive: "chip-grey", flagged: "chip-warn" } as const;

export default function SourceCard({ item, onView }: { item: SourceItem; onView: (item: SourceItem) => void }) {
  const [open, setOpen] = useState(false);
  const { authority: a, check: c } = item;
  const reason = c?.reason || (a ? "Not yet checked by the Citation Firewall" : "");
  const url = c?.url || a?.url;
  return (
    <li
      id={`src-card-${item.key}`}
      data-src={item.key}
      tabIndex={-1}
      className={`card p-3 ${item.status === "blocked" ? "!border-red-300" : ""}`}
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <CheckBadge status={item.status} />
        {a?.rank && (
          <span className={`chip ${RANK_CLS[a.rank.status]}`} title={a.rank.reason}>
            {a.rank.status === "binding" ? "Binding" : a.rank.status === "persuasive" ? "Persuasive" : "Flagged"}
          </span>
        )}
        {item.adverse && <span className="chip chip-bad" title={a?.adverse_reason}>Adverse</span>}
      </div>
      <h4 className="mt-1.5 font-semibold leading-snug text-navy">
        {item.caseName ? <i>{item.caseName}</i> : <span className="text-muted">Unknown case</span>}
      </h4>
      <p className="font-mono text-xs text-ink/80">{item.citation}{a?.year ? ` (${a.year})` : ""}</p>
      {a?.rank && <p className="mt-0.5 text-xs text-muted">{a.rank.reason}</p>}
      {item.adverse && a?.adverse_reason && <p className="mt-1 text-xs text-bad">{a.adverse_reason}</p>}
      {reason && <p className="mt-1 text-[13px]">{reason}</p>}
      {c?.treatment?.map((t, i) => <p key={i} className="text-xs text-amber-dark">Treatment: {t}</p>)}
      {a?.proposition && <p className="mt-1 text-xs text-muted">Cited for: {a.proposition}</p>}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {c && c.gates.length > 0 && (
          <button className="btn btn-sm" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
            {open ? "Hide" : "Show"} gates G1-G4
          </button>
        )}
        {item.opinionId != null && <button className="btn btn-sm" onClick={() => onView(item)}>View opinion</button>}
        {url && <a className="text-xs text-navy underline" href={url} target="_blank" rel="noreferrer">Source link</a>}
      </div>
      {open && c && (
        <ol className="mt-2 space-y-1 border-t border-line pt-2">
          {c.gates.map((g) => (
            <li key={g.gate} className="flex items-start gap-2 text-xs">
              <span className="w-6 flex-none font-bold text-navy">G{g.gate}</span>
              <span className={`chip ${OUT[g.outcome]?.c ?? "chip-grey"} flex-none`}>{OUT[g.outcome]?.t ?? g.outcome}</span>
              <span className="min-w-0">
                <span className="font-medium">{GATE_NAME[g.gate]}</span>
                {g.score != null && <span className="text-muted"> (score {g.score.toFixed(2)})</span>}
                {g.detail && <span className="block text-muted">{g.detail}</span>}
              </span>
            </li>
          ))}
        </ol>
      )}
    </li>
  );
}
