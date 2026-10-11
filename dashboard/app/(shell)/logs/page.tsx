"use client";
// Log Analysis — live event stream with filter chips and detail inspector.
import { useEffect, useMemo, useState } from "react";
import { getLogEvents } from "@/lib/api";
import { streamRunEvents } from "@/lib/sse";
import type { LogEvent } from "@/lib/types";
import { Card, CardHeader } from "@/components/ui/primitives";

const LEVEL_COLOR: Record<string, string> = { info: "#8B8D93", warn: "#F59E0B", error: "#EF4444" };
const RUN_ID = "r-full-1";

export default function LogsPage() {
  const [events, setEvents] = useState<LogEvent[]>([]);
  const [live, setLive] = useState(false);
  const [levels, setLevels] = useState<Set<string>>(new Set(["info", "warn", "error"]));
  const [selected, setSelected] = useState<LogEvent | null>(null);

  useEffect(() => {
    getLogEvents(RUN_ID).then(setEvents);
  }, []);

  useEffect(() => {
    if (!live) return;
    const lastSeq = events.length ? Math.max(...events.map((e) => e.seq)) : 0;
    const stop = streamRunEvents(RUN_ID, (e) => {
      setEvents((prev) => (prev.some((x) => x.seq === e.seq) ? prev : [...prev, e]));
    }, { lastEventId: lastSeq });
    return stop;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [live]);

  const toggleLevel = (l: string) => {
    setLevels((prev) => {
      const next = new Set(prev);
      next.has(l) ? next.delete(l) : next.add(l);
      return next;
    });
  };

  const filtered = useMemo(
    () => events.filter((e) => levels.has(e.level)).sort((a, b) => b.seq - a.seq),
    [events, levels],
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Log Analysis</h1>
          <div className="text-xs text-muted mt-1 font-mono">{RUN_ID}</div>
        </div>
        <button
          onClick={() => setLive((v) => !v)}
          className={`px-4 py-2 rounded-lg text-sm font-medium ${
            live ? "bg-fail/15 text-fail" : "bg-accent text-black hover:bg-accentHover"
          }`}
        >
          {live ? "Stop live tail" : "Start live tail"}
        </button>
      </div>

      <Card>
        <CardHeader
          title="Event Stream"
          right={
            <div className="flex gap-2">
              {(["info", "warn", "error"] as const).map((l) => (
                <button
                  key={l}
                  onClick={() => toggleLevel(l)}
                  className={`px-3 py-1 rounded-lg text-xs ${
                    levels.has(l) ? "bg-cardHover text-text border border-border" : "text-faint"
                  }`}
                >
                  <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full" style={{ background: LEVEL_COLOR[l] }} />
                  {l}
                </button>
              ))}
            </div>
          }
        />
        <div className="font-mono text-xs space-y-1 max-h-[480px] overflow-y-auto">
          {filtered.map((e) => (
            <button
              key={e.seq}
              onClick={() => setSelected(e)}
              className={`w-full flex items-center gap-3 px-2 py-1.5 rounded text-left hover:bg-cardHover ${
                selected?.seq === e.seq ? "bg-cardHover" : ""
              }`}
            >
              <span className="text-faint tabular-nums w-8">{e.seq}</span>
              <span className="text-faint tabular-nums">{e.ts.slice(11, 19)}</span>
              <span style={{ color: LEVEL_COLOR[e.level] }} className="w-12">{e.level}</span>
              <span className="text-accent w-32">{e.type}</span>
              {e.probeId && <span className="text-muted w-20">{e.probeId}</span>}
              <span className="text-text truncate">{e.detail ?? ""}</span>
            </button>
          ))}
          {filtered.length === 0 && <div className="py-6 text-center text-faint">No events match.</div>}
        </div>
      </Card>

      {selected && (
        <Card>
          <CardHeader title={`Event #${selected.seq} — ${selected.type}`} />
          <pre className="bg-[#0D0D0F] border border-border rounded-lg p-3 text-xs text-text font-mono whitespace-pre-wrap">
            {JSON.stringify(selected, null, 2)}
          </pre>
        </Card>
      )}
    </div>
  );
}
