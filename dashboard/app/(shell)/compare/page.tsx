"use client";
// Compare Runs — pick any two finished runs and see the security delta:
// score movement, per-severity finding movement, probes fixed vs regressed.
// This is the page that proves a hardening change actually worked.
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { getCompare, getRuns } from "@/lib/api";
import type { CompareResult, RecentRun, RiskBand } from "@/lib/types";
import { Card, CardHeader, SeverityPill } from "@/components/ui/primitives";
import { bandColor } from "@/lib/scoring";

function RunSelect({
  label, runs, value, onChange,
}: {
  label: string;
  runs: RecentRun[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <label className="flex-1 block">
      <div className="text-[11px] font-semibold tracking-wider text-faint mb-1">{label}</div>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-fg"
      >
        <option value="">Select a run…</option>
        {runs.map((r) => (
          <option key={r.runId} value={r.runId}>
            {r.name} · {r.target} · {new Date(r.executedOn).toLocaleString()}
          </option>
        ))}
      </select>
    </label>
  );
}

function SideCard({ title, result, side }: { title: string; result: CompareResult; side: "a" | "b" }) {
  const s = result[side];
  return (
    <Card>
      <CardHeader title={title} tooltip={`${s.runId} · ${s.suite} suite`} />
      <div className="flex items-end gap-6">
        <div>
          <div className="text-3xl font-bold" style={{ color: bandColor(s.band as RiskBand) }}>{s.score}</div>
          <div className="text-xs text-muted">risk score · {s.band}</div>
        </div>
        <div>
          <div className="text-xl font-semibold">{s.findingCount}</div>
          <div className="text-xs text-muted">findings</div>
        </div>
        <div>
          <div className="text-xl font-semibold">{s.simulated}</div>
          <div className="text-xs text-muted">probes simulated</div>
        </div>
        <div className="flex-1 text-right text-xs text-faint">
          {s.status} · {new Date(s.executedOn ?? Date.now()).toLocaleString()}
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {Object.entries(s.bySeverity).length === 0 && (
          <span className="text-xs text-faint">No findings — clean run.</span>
        )}
        {Object.entries(s.bySeverity).map(([sev, count]) => (
          <div key={sev} className="flex items-center gap-2 border border-border rounded-lg px-3 py-1.5">
            <SeverityPill severity={sev} />
            <span className="text-sm font-semibold">{count}</span>
          </div>
        ))}
      </div>
      {Object.keys(s.failingProbes).length > 0 && (
        <div className="mt-4 text-xs text-muted">
          <span className="font-semibold text-fg">Failing probes: </span>
          {Object.entries(s.failingProbes).map(([pid, sev]) => (
            <span key={pid} className="mr-2 inline-flex items-center gap-1 align-middle">
              <code className="text-accent">{pid}</code>
              <SeverityPill severity={sev} />
            </span>
          ))}
        </div>
      )}
    </Card>
  );
}

function CompareInner() {
  const params = useSearchParams();
  const [runs, setRuns] = useState<RecentRun[]>([]);
  const [a, setA] = useState(params.get("a") ?? "");
  const [b, setB] = useState(params.get("b") ?? "");
  const [result, setResult] = useState<CompareResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { getRuns().then(setRuns).catch(() => {}); }, []);

  const load = useCallback(() => {
    if (!a || !b) return;
    setLoading(true);
    getCompare(a, b)
      .then((r) => { setResult(r); setError(null); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [a, b]);

  useEffect(() => { load(); }, [load]);

  const finished = useMemo(
    () => runs.filter((r) => r.status === "DONE" || r.status === "FAILED"),
    [runs],
  );

  const sevKeys = useMemo(() => {
    if (!result) return [];
    const keys = new Set([...Object.keys(result.a.bySeverity), ...Object.keys(result.b.bySeverity)]);
    return [...keys];
  }, [result]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Compare Runs</h1>
        <div className="text-xs text-muted mt-1">
          Did your prompt-hardening change actually reduce risk? Pick a before-run and an after-run.
        </div>
      </div>

      <Card>
        <div className="flex flex-col md:flex-row gap-4 items-end">
          <RunSelect label="RUN A (BEFORE)" runs={finished} value={a} onChange={setA} />
          <RunSelect label="RUN B (AFTER)" runs={finished} value={b} onChange={setB} />
          <button
            onClick={load}
            disabled={!a || !b || loading}
            className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium hover:bg-accentHover disabled:opacity-40"
          >
            {loading ? "Comparing…" : "Compare"}
          </button>
        </div>
      </Card>

      {error && <div className="text-red-300 font-mono text-sm">{error}</div>}

      {result && (
        <>
          <Card>
            <CardHeader title="Delta" tooltip="Run B minus Run A. Negative score delta = improvement." />
            <div className="flex flex-wrap items-center gap-8">
              <div>
                <div
                  className="text-3xl font-bold"
                  style={{ color: result.deltaScore <= 0 ? "#34D399" : "#F87171" }}
                >
                  {result.deltaScore > 0 ? "+" : ""}{result.deltaScore}
                </div>
                <div className="text-xs text-muted">score delta</div>
              </div>
              {sevKeys.length > 0 ? sevKeys.map((sev) => {
                const d = result.severityDelta[sev] ?? 0;
                return (
                  <div key={sev}>
                    <div className="text-xl font-semibold" style={{ color: d < 0 ? "#34D399" : d > 0 ? "#F87171" : undefined }}>
                      {d > 0 ? "+" : ""}{d}
                    </div>
                    <div className="text-xs text-muted flex items-center gap-1">
                      <SeverityPill severity={sev} /> findings
                    </div>
                  </div>
                );
              }) : <span className="text-sm text-faint">No findings in either run.</span>}
            </div>
            {(result.fixedInB.length > 0 || result.newInB.length > 0) && (
              <div className="mt-5 grid md:grid-cols-2 gap-4 text-sm">
                <div className="border border-border rounded-lg p-4">
                  <div className="text-xs font-semibold tracking-wider text-faint mb-2">FIXED IN RUN B</div>
                  {result.fixedInB.length === 0
                    ? <span className="text-xs text-faint">Nothing fixed — same failures.</span>
                    : result.fixedInB.map((p) => (
                        <div key={p} className="text-green-300">✓ <code>{p}</code></div>
                      ))}
                </div>
                <div className="border border-border rounded-lg p-4">
                  <div className="text-xs font-semibold tracking-wider text-faint mb-2">NEW IN RUN B</div>
                  {result.newInB.length === 0
                    ? <span className="text-xs text-faint">No regressions.</span>
                    : result.newInB.map((p) => (
                        <div key={p} className="text-red-300">✗ <code>{p}</code></div>
                      ))}
                </div>
              </div>
            )}
          </Card>

          <SideCard title="RUN A" result={result} side="a" />
          <SideCard title="RUN B" result={result} side="b" />
        </>
      )}

      {!result && !error && (
        <div className="text-sm text-faint">Select two runs above to see the delta.</div>
      )}
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<div className="text-muted">Loading…</div>}>
      <CompareInner />
    </Suspense>
  );
}
