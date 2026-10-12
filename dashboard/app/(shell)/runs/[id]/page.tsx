"use client";
// Run Detail — per-suite summary, findings table with quoted evidence.
// Live mode polls while the run is in flight, so the demo shows scores and
// findings appearing as the engine works.
import { useCallback, useEffect, useState } from "react";
import { getRunDetail, liveRunReport } from "@/lib/api";
import type { RunDetail as RunDetailT } from "@/lib/types";
import { Card, CardHeader, SeverityPill, StatusPill } from "@/components/ui/primitives";
import { DonutRing } from "@/components/charts/DonutRing";
import { bandColor } from "@/lib/scoring";

const ACTIVE = new Set(["QUEUED", "PLAN", "EXECUTE", "JUDGE", "MUTATE", "REPORT"]);

export default function RunDetailPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [run, setRun] = useState<RunDetailT | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(() => {
    getRunDetail(id).then((r) => { setRun(r); setError(null); })
      .catch((e) => setError(String(e)));
  }, [id]);

  useEffect(() => {
    load();
    const t = setInterval(() => {
      setRun((cur) => {
        if (!cur || ACTIVE.has(cur.status)) load();
        return cur;
      });
    }, 2000);
    return () => clearInterval(t);
  }, [load]);

  if (error) return <div className="text-red-300 font-mono text-sm">{error}</div>;
  if (!run) return <div className="text-muted">Loading…</div>;

  const running = ACTIVE.has(run.status);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-3">
            {run.name}
            <StatusPill status={run.status} />
          </h1>
          <div className="text-xs text-muted mt-1 font-mono">{run.runId} · {run.target}</div>
        </div>
        <div className="flex gap-3">
          <button className="px-4 py-2 rounded-lg border border-border text-sm hover:bg-cardHover">Re-run</button>
          <button
            disabled={running}
            onClick={() => liveRunReport(run.runId)}
            className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium hover:bg-accentHover disabled:opacity-40"
          >
            {running ? "Running…" : "Download Report"}
          </button>
        </div>
      </div>

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
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
