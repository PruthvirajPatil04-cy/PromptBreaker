// SSE client with Last-Event-ID replay support. In mock mode it replays the
// fixture events on a timer so Overview/Log feel live before the engine lands.
import type { LogEvent } from "./types";
import { logEvents as mockEvents } from "./mock";

export type EventHandler = (e: LogEvent) => void;

const USE_MOCK = true;

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

  const url = `${process.env.NEXT_PUBLIC_PB_API_BASE ?? "http://localhost:8000"}/v1/runs/${runId}/events`;
  const source = new EventSource(url);

  const types = ["run.started", "probe.sent", "probe.judged", "probe.error", "run.finished", "run.failed"];
  const handler = (ev: MessageEvent) => {
    try {
      const payload = JSON.parse(ev.data);
      onEvent({
        seq: Number(ev.lastEventId ?? 0),
        runId,
        type: ev.type,
        ts: new Date().toISOString(),
        level: ev.type.includes("error") || ev.type.includes("failed") ? "error" : ev.type.includes("judged") ? "warn" : "info",
        detail: JSON.stringify(payload),
      });
    } catch (err) {
      opts.onError?.(err);
    }
  };
  types.forEach((t) => source.addEventListener(t, handler as EventListener));

  return () => source.close();
}
