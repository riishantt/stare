import { useEffect, useRef } from "react";
import { tokenStore } from "../api/client";
import type { TraceEvent } from "../api/types";

const TERMINAL = ["exported", "cancelled", "failed"];

/**
 * Subscribes to the run's SSE stream. `trace` events carry a TraceEvent; `status` events carry
 * {status}. EventSource reconnects by itself; the server replays persisted steps first, so callers
 * must de-duplicate by `seq`.
 */
export function useRunEvents(
  runId: number | null,
  handlers: { onTrace: (e: TraceEvent) => void; onStatus: (status: string) => void; onOpen?: () => void },
) {
  const h = useRef(handlers);
  h.current = handlers;
  useEffect(() => {
    if (runId == null) return;
    const token = tokenStore.get();
    if (!token) return;
    const es = new EventSource(`/api/runs/${runId}/events?token=${encodeURIComponent(token)}`);
    es.addEventListener("open", () => h.current.onOpen?.());
    es.addEventListener("trace", (ev) => {
      try { h.current.onTrace(JSON.parse((ev as MessageEvent).data) as TraceEvent); } catch { /* ignore */ }
    });
    es.addEventListener("status", (ev) => {
      try {
        const d = JSON.parse((ev as MessageEvent).data) as { status: string };
        h.current.onStatus(d.status);
        // the server ends the stream on terminal states; stop EventSource from reconnecting forever
        if (TERMINAL.includes(d.status)) es.close();
      } catch { /* ignore */ }
    });
    return () => es.close();
  }, [runId]);
}
