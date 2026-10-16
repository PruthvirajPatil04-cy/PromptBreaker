"use client";
// Overview — matches the reference layout: Overall Score + Category Scores,
// Recent Test Runs table, Categories Overview cards.
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { getOverview, USE_MOCK } from "@/lib/api";
import { streamRunEvents } from "@/lib/sse";
import type { OverviewPayload } from "@/lib/types";
import { StartScanModal } from "@/components/StartScanModal";
import { GaugeChart } from "@/components/charts/GaugeChart";
import { SparkTrend } from "@/components/charts/SparkTrend";
import { ScoreBar } from "@/components/charts/ScoreBar";
import { SegmentsProgress } from "@/components/charts/SegmentsProgress";
import { DonutRing } from "@/components/charts/DonutRing";
import {
  Card, CardHeader, InfoTooltip, ScoreBadge, StatusPill, CountPill, ProbeTag,
} from "@/components/ui/primitives";
import { riskBand, bandColor } from "@/lib/scoring";

const MOCK_TREND = [52, 48, 55, 49, 44, 47, 46];
const ACTIVE_STATUSES = new Set(["QUEUED", "PLAN", "EXECUTE", "JUDGE", "MUTATE", "REPORT"]);

export default function OverviewPage() {
  const [data, setData] = useState<OverviewPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState(false);
  const [view, setView] = useState<"score" | "trend">("score");

  useEffect(() => {
    // Re-run flow: run detail's "Re-run" lands here with ?rescan=1 so the
    // Start Scan form opens immediately (API keys are never stored — a re-run
    // always resupplies them, by design).
    if (typeof window !== "undefined" &&
        new URLSearchParams(window.location.search).has("rescan")) {
      setModal(true);
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, []);

  const load = useCallback(() => {
    getOverview().then((d) => { setData(d); setError(null); })
      .catch((e) => setError(String(e)));
  }, []);

  // A2: live feed — tail the newest in-flight run over SSE so its progress
  // row and verdict counts move as the engine works (poll stays as fallback).
  const activeRunId =
    data?.recentRuns.find((r) => ACTIVE_STATUSES.has(r.status))?.runId ?? "";
  const reloadTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (USE_MOCK || !activeRunId) return;
    const stop = streamRunEvents(activeRunId, (e) => {
      if (e.type === "run.finished" || e.type === "run.failed") {
        load(); // run landed — refresh everything at once
      } else if (e.type === "probe.judged" && !reloadTimer.current) {
        reloadTimer.current = setTimeout(() => {
          reloadTimer.current = null;
          load();
        }, 800);
      }
    });
    return () => {
      stop();
      if (reloadTimer.current) { clearTimeout(reloadTimer.current); reloadTimer.current = null; }
    };
  }, [activeRunId, load]);

  useEffect(() => {
    load();
    // live mode: refresh while a run is queued/running so progress moves
    if (USE_MOCK) return;
    const t = setInterval(() => {
      setData((cur) => {
        const active = cur?.recentRuns?.some((r) => r.status === "QUEUED" || r.status === "EXECUTE");
        if (active) load();
        return cur;
      });
    }, 3000);
    return () => clearInterval(t);
  }, [load]);

  if (error) return <ErrorBanner error={error} onRetry={load} />;
  if (!data) return <div className="text-muted">Loading…</div>;

  const o = data.overall;
  const band = riskBand(o.score);
  const trend = USE_MOCK && o.trend.length < 2 ? MOCK_TREND : o.trend;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Overview</h1>
        <div className="flex items-center gap-3">
          {activeRunId && !USE_MOCK && (
            <span
              className="inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded bg-fail/15 text-fail font-medium"
              title="Engine events streaming live for the in-flight run"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-fail animate-pulse" />
              LIVE
            </span>
          )}
          <button className="px-4 py-2 rounded-lg border border-border text-sm text-text hover:bg-cardHover">
            Generate Report
          </button>
          <button
            onClick={() => setModal(true)}
            className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium hover:bg-accentHover"
          >
            New Test Run +
          </button>
        </div>
      </div>

      {modal && <StartScanModal onClose={() => setModal(false)} />}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Overall Score */}
        <Card className="lg:col-span-2">
          <CardHeader
            title="Overall Score"
            tooltip="Weighted mean of category scores. Bands: ≥76 Low, 51–75 Moderate, 26–50 High, <25 Critical."
            right={
              <div className="flex gap-1">
                <button
                  onClick={() => setView("score")}
                  className={`h-7 w-7 rounded ${view === "score" ? "bg-accent/20 text-accent" : "text-muted"}`}
                >◉</button>
                <button
                  onClick={() => setView("trend")}
                  className={`h-7 w-7 rounded ${view === "trend" ? "bg-accent/20 text-accent" : "text-muted"}`}
                >◺</button>
              </div>
            }
          />
          <div className="flex items-center gap-8">
            <div className="space-y-3">
              {[
                ["Latest test run execution", o.lastRunAt ? o.lastRunAt.slice(0, 10) : "—"],
                ["Simulated attacks", String(o.simulated)],
                ["Successful attacks", String(o.successful)],
              ].map(([label, value]) => (
                <div key={label} className="bg-[#0D0D0F] border border-border rounded-lg px-4 py-3 w-56">
                  <div className="text-xs text-muted">{label}</div>
                  <div className="text-lg font-semibold mt-0.5">{value}</div>
                </div>
              ))}
            </div>
            <div className="flex-1 flex flex-col items-center justify-center relative">
              {view === "score" ? (
                <>
                  <GaugeChart value={o.score} size={240} />
                  <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center mt-4">
                    <span
                      className="text-xs font-semibold px-2 py-[2px] rounded-full border"
                      style={{ color: bandColor(band), borderColor: bandColor(band) }}
                    >
                      {band} Risk
                    </span>
                    <span className="text-5xl font-bold mt-1 tabular-nums">{Math.round(o.score)}</span>
                  </div>
                </>
              ) : (
                <SparkTrend points={trend} width={280} height={140} />
              )}
            </div>
          </div>
        </Card>

        {/* Category Scores */}
        <Card>
          <CardHeader title="Category Scores" tooltip="Score per category. Higher is safer." />
          {o.categories.map((c) => (
            <ScoreBar key={c.category} label={c.category} score={c.score} />
          ))}
        </Card>
      </div>

      {/* Recent Test Runs */}
      <Card>
        <CardHeader
          title="Recent Test Runs"
          right={<Link href="/runs" className="text-accent text-sm hover:underline">See All ›</Link>}
        />
        {data.recentRuns.length === 0 ? (
          <div className="py-12 text-center space-y-3">
            <div className="text-text font-medium">No assessments yet</div>
            <p className="text-sm text-muted max-w-md mx-auto">
              Configure an authorized target in Target Settings, then start your first
              adversarial scan. The scope gate requires an attestation on every run.
            </p>
            <button
              onClick={() => setModal(true)}
              className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium hover:bg-accentHover"
            >
              New Test Run +
            </button>
          </div>
        ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-faint border-b border-border">
              <th className="pb-3 font-medium">NAME</th>
              <th className="pb-3 font-medium">EXECUTED ON</th>
              <th className="pb-3 font-medium">PROBES</th>
              <th className="pb-3 font-medium">RESULT ⇅</th>
              <th className="pb-3 font-medium">PROGRESS</th>
              <th className="pb-3" />
            </tr>
          </thead>
          <tbody>
            {data.recentRuns.map((r) => (
              <tr key={r.runId} className="border-b border-border/50 hover:bg-cardHover/50">
                <td className="py-4 text-text">{r.name}</td>
                <td className="py-4 text-muted tabular-nums">
                  {r.executedOn.slice(0, 10)}, {r.executedOn.slice(11, 16)}
                </td>
                <td className="py-4"><ProbeTag probes={r.probes} /></td>
                <td className="py-4">
                  <span className="flex items-center gap-3">
                    <CountPill n={r.passed} kind="passed" />
                    <CountPill n={r.failed} kind="failed" />
                    <CountPill n={r.errors} kind="error" />
                  </span>
                </td>
                <td className="py-4">
                  <SegmentsProgress pct={r.progressPct} status={r.status} />
                </td>
                <td className="py-4 text-right">
                  <Link
                    href={`/runs/${r.runId}`}
                    className="px-3 py-1.5 rounded-lg border border-border text-xs text-text hover:bg-cardHover"
                  >
                    Details
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        )}
      </Card>

      {/* Categories Overview */}
      <Card>
        <CardHeader title="Categories Overview" />
        {data.suitesByCategory.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted">
            Category breakdowns appear after your first run completes.
          </div>
        ) : null}
        {data.suitesByCategory.map((cat) => (
          <div key={cat.category} className="mb-6 last:mb-0">
            <div className="flex items-center gap-3 mb-3">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-muted">
                <path d="M6 9l6 6 6-6" />
              </svg>
              <span className="font-semibold text-text">{cat.category}</span>
              <ScoreBadge score={cat.score} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
              {cat.suites.map((s) => (
                <div key={s.suiteId} className="bg-[#0D0D0F] border border-border rounded-xl p-4 flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="font-semibold text-text text-sm truncate">{s.name}</span>
                      <StatusPill status={s.status} />
                    </div>
                    <div className="text-xs text-faint tabular-nums mb-3">{s.executedOn.slice(0, 10)}, {s.executedOn.slice(11, 16)}</div>
                    <div className="space-y-1">
                      <CountPill n={s.passed} kind="passed" />
                      <div><CountPill n={s.failed} kind="failed" /></div>
                      <div><CountPill n={s.errors} kind="error" /></div>
                    </div>
                  </div>
                  <div className="ml-3 shrink-0">
                    <DonutRing passed={s.passed} failed={s.failed} dim={s.status === "PENDING"} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </Card>
    </div>
  );
}

/** Fail loudly: live-mode API problems must never fall back to mock numbers. */
function ErrorBanner({ error, onRetry }: { error: string; onRetry: () => void }) {
  return (
    <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-6 space-y-3">
      <div className="flex items-center gap-2 text-red-300 font-semibold">
        <span className="h-2 w-2 rounded-full bg-red-400" />
        Engine unreachable
      </div>
      <p className="text-sm text-red-200/80 font-mono break-all">{error}</p>
      <p className="text-xs text-muted">
        The dashboard will not show cached/mock numbers while live data is expected.
        Check that the promptbreaker API service is running.
      </p>
      <button
        onClick={onRetry}
        className="px-4 py-2 rounded-lg border border-red-400/40 text-sm text-red-200 hover:bg-red-500/20"
      >
        Retry
      </button>
    </div>
  );
}
