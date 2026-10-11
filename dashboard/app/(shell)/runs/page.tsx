"use client";
// Test Runs — full run list with filters.
import { useEffect, useState } from "react";
import Link from "next/link";
import { getOverview } from "@/lib/api";
import type { RecentRun } from "@/lib/types";
import { Card, CountPill, ProbeTag } from "@/components/ui/primitives";
import { SegmentsProgress } from "@/components/charts/SegmentsProgress";

const FILTERS = ["All", "Manual", "CI/CD", "Running", "Completed"] as const;

export default function RunsPage() {
  const [runs, setRuns] = useState<RecentRun[]>([]);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("All");
  const [q, setQ] = useState("");

  useEffect(() => { getOverview().then((d) => setRuns(d.recentRuns)); }, []);

  const filtered = runs.filter((r) => {
    const matchQ = r.name.toLowerCase().includes(q.toLowerCase());
    const matchF =
      filter === "All" ||
      (filter === "Manual" && r.source === "manual") ||
      (filter === "CI/CD" && r.source !== "manual") ||
      (filter === "Running" && (r.status === "EXECUTE" || r.status === "QUEUED")) ||
      (filter === "Completed" && r.status === "DONE");
    return matchQ && matchF;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Test Runs</h1>
        <button className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium hover:bg-accentHover">
          New Test Run +
        </button>
      </div>

      <Card>
        <div className="flex items-center gap-3 mb-4">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search runs…"
            className="w-64 bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent"
          />
          <div className="flex gap-1">
            {FILTERS.map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded-lg text-xs ${
                  filter === f ? "bg-accent/15 text-accent" : "text-muted hover:text-text"
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-faint border-b border-border">
              <th className="pb-3 font-medium">NAME</th>
              <th className="pb-3 font-medium">EXECUTED ON</th>
              <th className="pb-3 font-medium">PROBES</th>
              <th className="pb-3 font-medium">RESULT</th>
              <th className="pb-3 font-medium">PROGRESS</th>
              <th className="pb-3" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
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
                <td className="py-4"><SegmentsProgress pct={r.progressPct} status={r.status} /></td>
                <td className="py-4 text-right">
                  <Link href={`/runs/${r.runId}`} className="px-3 py-1.5 rounded-lg border border-border text-xs hover:bg-cardHover">
                    Details
                  </Link>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={6} className="py-8 text-center text-faint">No runs match.</td></tr>
            )}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
