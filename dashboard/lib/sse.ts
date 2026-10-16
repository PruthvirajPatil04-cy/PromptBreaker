// SSE client with Last-Event-ID replay support. In mock mode it replays the
// fixture events on a timer so Overview/Log feel live before the engine lands.
// Live mode: GET /v1/runs/{id}/events with Accept: text/event-stream (the API
// serves JSON by default, SSE when asked). EventSource cannot set headers, so
// the API key travels as ?key=.
import type { LogEvent } from "./types";
import { logEvents as mockEvents } from "./mock";
import { USE_MOCK } from "./api";

export type EventHandler = (e: LogEvent) => void;

const API_BASE = process.env.NEXT_PUBLIC_PB_API_BASE ?? "";
const API_KEY = process.env.NEXT_PUBLIC_PB_API_KEY ?? "";

const TYPES = [
  "run.started", "probe.sent", "probe.judged", "probe.error",
  "run.finished", "run.failed", "run.rejected", "ping",
];

export function streamRunEvents(
  runId: string,
  onEvent: EventHandler,
  opts: { lastEventId?: number; onError?: (err: unknown) => void } = {},
): () => void {
  if (USE_MOCK) {
    // Replay fixture events on a short timer, then stop.
    const queue = mockEvents.filter((e) => e.runId === runId && e.seq > (opts.lastEventId ?? 0));
    let i = 0;
    const timer = setInterval(() => {
      if (i >= queue.length) {
        clearInterval(timer);
        return;
      }
      onEvent(queue[i++]);
    }, 400);
    return () => clearInterval(timer);
  }

  const qs = new URLSearchParams();
  if (API_KEY) qs.set("key", API_KEY);
  if (opts.lastEventId) qs.set("lastEventId", String(opts.lastEventId));
  const url = `${API_BASE}/v1/runs/${runId}/events?${qs.toString()}`;
  const source = new EventSource(url);

  const handler = (ev: MessageEvent) => {
    if (ev.data === "{}" || ev.type === "ping") return; // keepalive
    try {
      const payload = JSON.parse(ev.data) as LogEvent;
      onEvent({
        ...payload,
        seq: Number(ev.lastEventId ?? payload.seq ?? 0),
        runId,
        type: payload.type ?? ev.type,
        ts: payload.ts ?? new Date().toISOString(),
        level: payload.level
          ?? (ev.type.includes("error") || ev.type.includes("failed")
            ? "error"
            : ev.type.includes("judged") ? "warn" : "info"),
      });
    } catch (err) {
      opts.onError?.(err);
    }
  };
  TYPES.forEach((t) => source.addEventListener(t, handler as EventListener));

  return () => source.close();
}
