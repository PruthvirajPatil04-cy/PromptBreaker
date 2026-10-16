"use client";
// Run Detail — per-suite summary, findings table with quoted evidence.
// LIVE: while the run is in flight this page tails the engine's SSE event
// stream (probe.sent → probe.judged → run.finished) and refreshes the detail
// on every verdict, so the demo shows scores and findings appearing as the
// engine works. A slow poll remains as the fallback if the stream drops.
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getRunDetail, liveRunReport, resumeRun, triageFinding } from "@/lib/api";
import { streamRunEvents } from "@/lib/sse";
import type { LogEvent, RunDetail as RunDetailT, TriageState } from "@/lib/types";
import { Card, CardHeader, SeverityPill, StatusPill } from "@/components/ui/primitives";
import { DonutRing } from "@/components/charts/DonutRing";
import { bandColor } from "@/lib/scoring";

const ACTIVE = new Set(["QUEUED", "PLAN", "EXECUTE", "JUDGE", "MUTATE", "REPORT"]);
type ReportFmt = "md" | "json" | "sarif";

/** SSE events carry the engine payload's snake_case keys spread in. */
type RawEvent = LogEvent & Record<string, unknown>;

const EVENT_COLOR: Record<string, string> = {
  "run.started": "#22C55E",
  "run.finished": "#22C55E",
  "run.failed": "#EF4444",
  "run.rejected": "#EF4444",
  "probe.sent": "#8B8D93",
  "probe.judged": "#F59E0B",
  "probe.error": "#EF4444",
};

const TRIAGE_OPTIONS: { value: TriageState; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "accepted_risk", label: "Accepted risk" },
  { value: "false_positive", label: "False positive" },
  { value: "patched", label: "Patched" },
];

const TRIAGE_COLOR: Record<TriageState, string> = {
  open: "#F59E0B",
  accepted_risk: "#22C55E",
  false_positive: "#8B8D93",
  patched: "#22C55E",
};

/** One-line human summary of an engine event's payload. */
function eventSummary(e: RawEvent): string {
  switch (e.type) {
    case "run.started":
      return `${e.suite ?? ""} · ${e.jobs ?? "?"} probe jobs · ${e.concurrency ?? 1} parallel`;
    case "probe.sent":
      return e.parent ? `mutation of ${e.parent}` : "base probe";
    case "probe.judged":
      return `${e.verdict ?? ""}${e.judge ? ` · judge: ${e.judge}` : ""}`;
    case "probe.error":
      return String(e.error ?? "");
    case "run.finished":
      return `${e.status ?? ""} · score ${e.score ?? "—"} (${e.band ?? "—"} risk) · ${e.attempts ?? "?"} attempts`;
    case "run.failed":
      return String(e.error ?? "");
    default:
      return "";
  }
}

export default function RunDetailPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const router = useRouter();
  const [run, setRun] = useState<RunDetailT | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [fmt, setFmt] = useState<ReportFmt>("md");
  const [events, setEvents] = useState<RawEvent[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [resuming, setResuming] = useState(false);
  const reloadTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(() => {
    getRunDetail(id)
      .then((r) => { setRun(r); setError(null); })
      .catch((e) => setError(String(e)));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const running = !!run && ACTIVE.has(run.status);

  // Slow fallback poll — only needed if the SSE stream is unavailable.
  useEffect(() => {
    if (!running) return;
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, [running, load]);

  // Live tail: subscribe while the run is in flight, refresh on verdicts.
  useEffect(() => {
    if (!running) return;
    setStreaming(true);
    const stop = streamRunEvents(id, (raw0) => {
      const e = raw0 as RawEvent;
      // engine payloads are snake_case — normalize for the renderer
      if (!e.probeId && typeof e.probe_id === "string") e.probeId = e.probe_id;
      setEvents((prev) =>
        prev.some((x) => x.seq === e.seq) ? prev : [e, ...prev].slice(0, 80),
      );
      const terminal = e.type === "run.finished" || e.type === "run.failed";
      if (terminal) {
        load(); // final state straight away
      } else if (e.type === "probe.judged" || e.type === "run.started") {
        // debounce refreshes so a fast run doesn't stampede the API
        if (!reloadTimer.current) {
          reloadTimer.current = setTimeout(() => {
            reloadTimer.current = null;
            load();
          }, 700);
        }
      }
    });
    return () => {
      stop();
      setStreaming(false);
      if (reloadTimer.current) { clearTimeout(reloadTimer.current); reloadTimer.current = null; }
    };
  }, [id, running, load]);

  const setTriage = (findingId: string, state: TriageState) => {
    setRun((cur) => cur && {
      ...cur,
      findings: cur.findings.map((f) =>
        f.id === findingId ? { ...f, triageState: state } : f),
    });
    triageFinding(findingId, state).catch(() => {
      load(); // rollback by re-reading the server's truth
    });
  };

  const resume = () => {
    setResuming(true);
    resumeRun(id)
      .then((r) => router.push(`/runs/${r.runId}`))
      .catch((e) => { setError(String(e)); setResuming(false); });
  };

  if (error && !run) return <div className="text-red-300 font-mono text-sm">{error}</div>;
  if (!run) return <div className="text-muted">Loading…</div>;

  const js = run.judgeSummary ?? { prefilter: 0, llm: 0, none: 0, dual: 0, manipulation: 0, humanReview: 0 };
  const judgeTotal = js.prefilter + js.llm + js.none + js.dual;
  const canResume = (run.status === "FAILED" || run.status === "CANCELED") && !run.resumedFrom;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-3">
            {run.name}
            <StatusPill status={run.status} />
            {streaming && (
              <span className="inline-flex items-center gap-1.5 text-[11px] px-2 py-[2px] rounded bg-fail/15 text-fail font-medium">
                <span className="h-1.5 w-1.5 rounded-full bg-fail animate-pulse" />
                LIVE
              </span>
            )}
          </h1>
          <div className="text-xs text-muted mt-1 font-mono">
            {run.runId} · {run.target}
            {run.resumedFrom && (
              <>
                {" · "}
                <Link href={`/runs/${run.resumedFrom}`} className="text-accent hover:underline">
                  resumed from {run.resumedFrom}
                </Link>
              </>
            )}
          </div>
        </div>
        <div className="flex gap-3 items-center">
          {canResume && (
            <button
              onClick={resume}
              disabled={resuming}
              className="px-4 py-2 rounded-lg border border-amber-500/50 text-amber-200 text-sm hover:bg-amber-500/10 disabled:opacity-40"
            >
              {resuming ? "Resuming…" : "Resume"}
            </button>
          )}
          <button
            onClick={() => router.push("/?rescan=1")}
            className="px-4 py-2 rounded-lg border border-border text-sm hover:bg-cardHover"
          >
            Re-run
          </button>
          <Link
            href={`/compare?a=${run.runId}`}
            className="px-4 py-2 rounded-lg border border-border text-sm hover:bg-cardHover"
          >
            Compare…
          </Link>
          <select
            aria-label="Report format"
            value={fmt}
            onChange={(e) => setFmt(e.target.value as ReportFmt)}
            className="bg-bg border border-border rounded-lg px-3 py-2 text-sm"
          >
            <option value="md">Markdown</option>
            <option value="json">JSON</option>
            <option value="sarif">SARIF</option>
          </select>
          <button
            disabled={running}
            onClick={() => liveRunReport(run.runId, fmt)}
            className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium hover:bg-accentHover disabled:opacity-40"
          >
            {running ? "Running…" : "Download"}
          </button>
        </div>
      </div>

      {error && (
        <div className="border border-red-500/40 bg-red-500/10 rounded-lg px-4 py-3 text-sm text-red-200 font-mono">
          {error}
        </div>
      )}

      {run.abortReason && !running && (
        <div className="border border-amber-500/40 bg-amber-500/10 rounded-lg px-4 py-3 text-sm text-amber-200">
          <span className="font-semibold">Run ended early: </span>
          <span className="font-mono text-xs">{run.abortReason}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader title="Score" />
          <div className="text-4xl font-bold tabular-nums" style={{ color: bandColor(run.band) }}>
            {run.score.toFixed(1)}
          </div>
          <div className="text-sm text-muted mt-1">{run.band} risk</div>
          <div className="mt-4 space-y-1 text-sm">
            <div className="flex justify-between"><span className="text-muted">Simulated</span><span className="tabular-nums">{run.simulated}</span></div>
            <div className="flex justify-between"><span className="text-muted">Successful</span><span className="tabular-nums text-fail">{run.successful}</span></div>
            <div className="flex justify-between"><span className="text-muted">Evidence chain</span><span className={run.evidenceChainValid ? "text-pass" : "text-fail"}>{run.evidenceChainValid ? "Valid ✓" : "BROKEN"}</span></div>
          </div>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title="Budget" />
          <div className="grid grid-cols-3 gap-4 text-sm">
            {([
              ["Probes", run.budget.probes.used, run.budget.probes.cap, ""],
              ["Tokens", run.budget.tokens.used, run.budget.tokens.cap, ""],
              ["Cost", run.budget.costUsd.used, run.budget.costUsd.cap, "$"],
            ] as [string, number, number, string][]).map(([label, u, c, pre]) => {
              const pct = Math.min(100, (u / c) * 100);
              return (
                <div key={label}>
                  <div className="text-muted mb-1">{label}</div>
                  <div className="text-text tabular-nums">{pre}{u.toLocaleString()} <span className="text-faint">/ {pre}{c.toLocaleString()}</span></div>
                  <div className="h-1.5 rounded-full bg-[#1F1F23] mt-2 overflow-hidden">
                    <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {/* Judge breakdown — which engine actually decided each verdict. */}
      <Card>
        <CardHeader
          title="Judge Breakdown"
          tooltip="Prefilter = deterministic signatures; LLM = model judged (quoted-span verified); dual = both agreed."
          right={<span className="text-xs text-muted">{judgeTotal} verdicts · {run.attemptCount} attempts</span>}
        />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {([
            ["Prefilter", js.prefilter, "#22C55E"],
            ["LLM judge", js.llm, "#60A5FA"],
            ["Dual", js.dual, "#A78BFA"],
            ["Undecided", js.none, "#8B8D93"],
          ] as [string, number, string][]).map(([label, count, color]) => (
            <div key={label} className="bg-[#0D0D0F] border border-border rounded-xl p-4">
              <div className="text-xs text-muted">{label}</div>
              <div className="text-2xl font-bold tabular-nums mt-1" style={{ color }}>{count}</div>
              <div className="h-1.5 rounded-full bg-[#1F1F23] mt-2 overflow-hidden">
                <div
                  className="h-full"
                  style={{ background: color, width: `${judgeTotal ? (count / judgeTotal) * 100 : 0}%` }}
                />
              </div>
            </div>
          ))}
        </div>
        <div className="flex gap-6 mt-4 text-xs">
          <span className={js.manipulation ? "text-warn" : "text-muted"}>
            ⚠ Judge manipulation attempts: <span className="font-semibold">{js.manipulation}</span>
          </span>
          <span className={js.humanReview ? "text-fail" : "text-muted"}>
            ⚠ Requires human review: <span className="font-semibold">{js.humanReview}</span>
          </span>
        </div>
      </Card>

      <Card>
        <CardHeader title="Suites" />
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
          {run.categories.map((c) => (
            <div key={c.category} className="bg-[#0D0D0F] border border-border rounded-xl p-4 flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-text">{c.category}</div>
                <div className="mt-2 space-y-1 text-xs">
                  <div><span className="text-pass font-semibold">{c.passed}</span> <span className="text-muted">Passed</span></div>
                  <div><span className="text-fail font-semibold">{c.failed}</span> <span className="text-muted">Failed</span></div>
                </div>
              </div>
              <DonutRing passed={c.passed} failed={c.failed} size={56} />
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader title={`Findings (${run.findings.length})`} />
        <div className="space-y-2">
          {run.findings.map((f) => (
            <div key={f.id} className="border border-border rounded-xl overflow-hidden">
              <button
                onClick={() => setOpen(open === f.id ? null : f.id)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-cardHover text-left"
              >
                <div className="flex items-center gap-3">
                  <SeverityPill severity={f.severity} />
                  <span className="text-sm text-text">{f.title}</span>
                  {f.judgeManipulation && (
                    <span className="text-[11px] px-2 py-[2px] rounded bg-warn/15 text-warn">judge manipulation</span>
                  )}
                  {f.triageState !== "open" && (
                    <span
                      className="text-[11px] px-2 py-[2px] rounded bg-cardHover"
                      style={{ color: TRIAGE_COLOR[f.triageState] }}
                    >
                      {TRIAGE_OPTIONS.find((o) => o.value === f.triageState)?.label}
                    </span>
                  )}
                </div>
                <span className="text-faint">{open === f.id ? "−" : "+"}</span>
              </button>
              {open === f.id && (
                <div className="px-4 pb-4 border-t border-border/50 pt-3 space-y-3 text-sm">
                  <div className="grid grid-cols-3 gap-4 text-xs">
                    <div><span className="text-muted">OWASP</span><div className="text-text mt-0.5">{f.owasp}</div></div>
                    <div><span className="text-muted">Judge</span><div className="text-text mt-0.5">{f.judgeEngine}</div></div>
                    <div><span className="text-muted">Evidence SHA-256</span><div className="text-text mt-0.5 font-mono">{f.evidenceSha256}</div></div>
                  </div>
                  <div>
                    <div className="text-xs text-muted mb-1">Judge rationale</div>
                    <div className="text-text">{f.judgeRationale}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted mb-1">Verbatim evidence</div>
                    <blockquote className="border-l-2 border-accent pl-3 py-1 bg-[#0D0D0F] rounded-r text-text font-mono text-xs">
                      {f.quotedSpan}
                    </blockquote>
                  </div>
                  {f.needsHumanReview && (
                    <div className="text-xs px-3 py-2 rounded bg-fail/10 text-fail">
                      ⚠ Critical finding — requires human review before report leaves the system.
                    </div>
                  )}
                  <div className="flex items-center gap-3 pt-1" onClick={(e) => e.stopPropagation()}>
                    <span className="text-xs text-muted">Triage</span>
                    <select
                      aria-label={`Triage state for ${f.id}`}
                      value={f.triageState}
                      onChange={(e) => setTriage(f.id, e.target.value as TriageState)}
                      className="bg-bg border border-border rounded-lg px-2 py-1 text-xs"
                    >
                      {TRIAGE_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                    <Link href="/review" className="text-xs text-accent hover:underline">
                      Review queue →
                    </Link>
                  </div>
                </div>
              )}
            </div>
          ))}
          {run.findings.length === 0 && (
            <div className="py-6 text-center text-faint text-sm">
              {running ? "No findings yet — the engine is still probing." : "No successful attacks. Target held."}
            </div>
          )}
        </div>
      </Card>

      {/* Live event tail — what the engine is doing right now. */}
      <Card>
        <CardHeader
          title="Live Engine Feed"
          right={
            <span className="text-xs text-muted font-mono">
              {streaming ? "streaming · SSE" : running ? "connecting…" : "idle"}
            </span>
          }
        />
        <div className="font-mono text-xs space-y-1 max-h-[300px] overflow-y-auto">
          {events.map((e) => (
            <div key={e.seq} className="flex items-center gap-3 px-2 py-1.5 rounded hover:bg-cardHover">
              <span className="text-faint tabular-nums w-8">{e.seq}</span>
              <span className="text-faint tabular-nums">{String(e.ts).slice(11, 19)}</span>
              <span className="w-24" style={{ color: EVENT_COLOR[e.type] ?? "#8B8D93" }}>{e.type}</span>
              {e.probeId && <span className="text-accent w-24">{e.probeId}</span>}
              <span className="text-text truncate">{eventSummary(e)}</span>
            </div>
          ))}
          {events.length === 0 && (
            <div className="py-6 text-center text-faint">
              {running ? "Waiting for engine events…" : "Run is not in flight — no live events."}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
