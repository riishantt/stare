export function fmtDate(s?: string | null): string {
  if (!s) return "";
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}
export function fmtTime(s?: string | null): string {
  if (!s) return "";
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
export function fmtSecs(ms?: number | null): string {
  if (ms == null) return "";
  return `${(ms / 1000).toFixed(1)} s`;
}
export const STATUTE_LABEL: Record<string, string> = { title_vii: "Title VII", ada: "ADA", adea: "ADEA" };
export function claimLabel(c: { statute?: string; theory?: string }): string {
  const s = STATUTE_LABEL[c.statute ?? ""] ?? c.statute ?? "";
  const t = (c.theory ?? "").replace(/_/g, " ");
  return [s, t].filter(Boolean).join(" ");
}
const PH = /(\[[A-Z][A-Z_]*(?:_\d+)?\])/g;
export function splitPlaceholders(text: string): { t: string; ph: boolean }[] {
  return text.split(PH).filter((x) => x !== "").map((t) => ({ t, ph: /^\[[A-Z][A-Z_]*(?:_\d+)?\]$/.test(t) }));
}
export function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
