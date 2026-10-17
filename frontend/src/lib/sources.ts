import type { Authority, CheckStatus, CitationCheck, RunOut } from "../api/types";

export interface SourceItem {
  key: string;
  authority: Authority | null;
  check: CitationCheck | null;
  status: CheckStatus;
  adverse: boolean;
  citation: string;
  caseName: string;
  opinionId: number | null;
  quote: string;
}

export const normCite = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "");

export function buildSources(run: RunOut | null): SourceItem[] {
  if (!run) return [];
  const checks = run.checks ?? [];
  const checkFor = (a: Authority): CitationCheck | null => {
    if (a.verification) return a.verification;
    const n = normCite(a.citation);
    const hits = checks.filter((c) => normCite(c.citation.cite) === n || (c.opinion_id != null && c.opinion_id === a.opinion_id));
    // prefer the memo-phase check (latest truth), else any
    return hits.find((c) => c.phase === "memo") ?? hits[hits.length - 1] ?? null;
  };
  const out: SourceItem[] = [];
  const seen = new Set<string>();
  const add = (a: Authority, adverse: boolean) => {
    const k = normCite(a.citation) || a.key;
    if (seen.has(k)) return;
    seen.add(k);
    const c = checkFor(a);
    out.push({
      key: a.key, authority: a, check: c, status: c?.status ?? "unresolved", adverse: adverse || a.adverse,
      citation: a.citation, caseName: a.case_name || c?.matched_case_name || c?.citation.case_name || "",
      opinionId: a.opinion_id ?? c?.opinion_id ?? null, quote: a.quote || c?.citation.quote || "",
    });
  };
  run.authorities.forEach((a) => add(a, false));
  run.adverse.forEach((a) => add(a, true));
  // checks that match no retained authority: blocked/unresolved citations the Firewall removed
  for (const c of checks) {
    const k = normCite(c.citation.cite);
    if (seen.has(k)) continue;
    seen.add(k);
    out.push({
      key: `chk:${k}`, authority: null, check: c, status: c.status, adverse: c.phase === "adverse",
      citation: c.citation.cite || c.citation.raw, caseName: c.matched_case_name || c.citation.case_name,
      opinionId: c.opinion_id ?? null, quote: c.citation.quote,
    });
  }
  return out;
}

export function findSource(items: SourceItem[], ref: { authority_key?: string | null; citation?: string }): SourceItem | undefined {
  return items.find((i) => ref.authority_key && i.key === ref.authority_key)
    ?? (ref.citation ? items.find((i) => normCite(i.citation) === normCite(ref.citation!)) : undefined);
}

export function scrollToSource(key: string) {
  const el = Array.from(document.querySelectorAll<HTMLElement>("[data-src]")).find((e) => e.dataset.src === key);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.remove("flash");
  void el.offsetWidth;
  el.classList.add("flash");
  el.focus({ preventScroll: true });
}
