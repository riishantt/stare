import { useState } from "react";
import type { SourceItem } from "../lib/sources";
import SourceCard from "./SourceCard";

type Filter = "all" | "support" | "adverse" | "blocked";
const isBlocked = (i: SourceItem) => i.status === "blocked" || i.status === "unresolved";

export default function SourcesPanel({ items, onView }: { items: SourceItem[]; onView: (i: SourceItem) => void }) {
  const [f, setF] = useState<Filter>("all");
  const counts = {
    all: items.length,
    support: items.filter((i) => !i.adverse && !isBlocked(i)).length,
    adverse: items.filter((i) => i.adverse).length,
    blocked: items.filter(isBlocked).length,
  };
  const shown = items.filter((i) => f === "all" || (f === "support" ? !i.adverse && !isBlocked(i) : f === "adverse" ? i.adverse : isBlocked(i)));
  const tabs: [Filter, string][] = [["all", "All"], ["support", "Support"], ["adverse", "Adverse"], ["blocked", "Blocked"]];
  return (
    <section className="card" aria-label="Sources and citation status">
      <div className="card-h"><h2>Sources and citation status</h2></div>
      <div role="tablist" aria-label="Filter sources" className="flex gap-1 border-b border-line px-3 pt-2">
        {tabs.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={f === k} onClick={() => setF(k)}
            className={`rounded-t-md border-b-2 px-3 py-1.5 text-sm font-semibold ${f === k ? "border-amber text-navy" : "border-transparent text-muted hover:text-navy"}`}>
            {label} <span className="text-xs font-normal">({counts[k]})</span>
          </button>
        ))}
      </div>
      <div className="card-b">
        {items.length === 0 ? (
          <p className="text-muted">No sources yet. Authorities appear here once the Research Agent has searched and the Citation Firewall has checked them.</p>
        ) : shown.length === 0 ? (
          <p className="text-muted">Nothing in this category.</p>
        ) : (
          <ul className="space-y-2.5">{shown.map((i) => <SourceCard key={i.key} item={i} onView={onView} />)}</ul>
        )}
      </div>
    </section>
  );
}
