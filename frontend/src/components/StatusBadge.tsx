import type { CheckStatus, RunStatus } from "../api/types";

export const CHECK_LABEL: Record<CheckStatus, { label: string; cls: string; icon: string }> = {
  verified: { label: "VERIFIED", cls: "chip-ok", icon: "✓" },
  warning: { label: "WARNING", cls: "chip-warn", icon: "!" },
  blocked: { label: "BLOCKED", cls: "chip-bad", icon: "✕" },
  unresolved: { label: "UNRESOLVED", cls: "chip-grey", icon: "?" },
};

export function CheckBadge({ status }: { status: CheckStatus }) {
  const c = CHECK_LABEL[status] ?? CHECK_LABEL.unresolved;
  return (
    <span className={`chip ${c.cls}`}>
      <span aria-hidden="true">{c.icon}</span>
      {c.label}
    </span>
  );
}

export function runStatusInfo(status: RunStatus, runNo?: number): { label: string; cls: string; busy: boolean } {
  const n = runNo ? `Run ${runNo}: ` : "";
  switch (status) {
    case "intake_running": return { label: `${n}reading documents`, cls: "chip-warn", busy: true };
    case "researching": return { label: `${n}in progress`, cls: "chip-warn", busy: true };
    case "awaiting_plan_approval": return { label: "Awaiting plan approval", cls: "chip-navy", busy: false };
    case "awaiting_memo_approval": return { label: "Awaiting memo approval", cls: "chip-navy", busy: false };
    case "approved": return { label: "Approved", cls: "chip-ok", busy: false };
    case "exported": return { label: "Exported", cls: "chip-ok", busy: false };
    case "failed": return { label: "Failed", cls: "chip-bad", busy: false };
    case "cancelled": return { label: "Cancelled", cls: "chip-grey", busy: false };
    default: return { label: status.replace(/_/g, " "), cls: "chip-grey", busy: false };
  }
}

export function RunStatusPill({ status, runNo }: { status: RunStatus; runNo?: number }) {
  const i = runStatusInfo(status, runNo);
  return (
    <span className={`chip ${i.cls} !text-[13px] !px-3 !py-1`}>
      {i.busy && <span className="dot dot-running" aria-hidden="true" />}
      {i.label}
    </span>
  );
}
