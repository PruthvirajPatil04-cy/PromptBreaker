"use client";
// Review Queue (C4) — open Critical/High findings awaiting a human call.
// This is the governance surface: every row shows the evidence the reviewer
// needs to decide, and the disposition (triage) lands on the finding itself,
// so it is durable, audited, and reflected in run detail + reports.
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { getReview, triageFinding } from "@/lib/api";
import type { ReviewItem, TriageState } from "@/lib/types";
import { Card, CardHeader, SeverityPill } from "@/components/ui/primitives";

const ACTIONS: { state: TriageState; label: string; color: string }[] = [
  { state: "false_positive", label: "False positive", color: "#8B8D93" },
  { state: "accepted_risk", label: "Accept risk", color: "#F59E0B" },
  { state: "patched", label: "Mark patched", color: "#22C55E" },
];

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [sevFilter, setSevFilter] = useState<"all" | "Critical" | "High">("all");

  const load = useCallback(() => {
    getReview().then((f) => { setItems(f); setError(null); })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => { load(); }, [load]);

  const dispose = async (item: ReviewItem, state: TriageState) => {
    setBusy(item.id);
    setItems((prev) => prev.filter((f) => f.id !== item.id)); // optimistic…
    try {
      await triageFinding(item.id, state);
    } catch (e) {
      setError(String(e));
      load(); // …rolled back from the server's truth on failure
    } finally {
      setBusy(null);
    }
  };

  const shown = items.filter((f) => sevFilter === "all" || f.severity === sevFilter);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Review Queue</h1>
          <div className="text-xs text-muted mt-1">
            Open Critical/High findings awaiting a human decision — dispositions persist to the store
            and annotate reports.
          </div>
        </div>
        <div className="flex gap-2 text-xs">
          {(["all", "Critical", "High"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSevFilter(s)}
              className={`px-3 py-1.5 rounded-lg border ${
                sevFilter === s ? "border-accent text-accent bg-accent/10" : "border-border text-muted"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="border border-red-500/40 bg-red-500/10 rounded-lg px-4 py-3 text-sm text-red-200 font-mono">
          {error}
        </div>
      )}

      {shown.length === 0 && !error && (
        <Card>
          <div className="py-12 text-center space-y-2">
            <div className="text-pass text-lg font-semibold">Queue clear ✓</div>
            <p className="text-sm text-muted">
              No open Critical/High findings. Run a scan or wait for scheduled scans to surface new ones.
            </p>
            <Link href="/" className="text-accent text-sm hover:underline">Back to Overview →</Link>
          </div>
        </Card>
      )}

      {shown.map((f) => (
        <Card key={f.id}>
          <CardHeader
            title={f.title}
            tooltip={`Run: ${f.runId} · finding: ${f.id}`}
            right={
              <div className="flex items-center gap-3">
                <SeverityPill severity={f.severity} />
                {f.needsHumanReview && (
                  <span className="text-[11px] px-2 py-[2px] rounded bg-fail/15 text-fail">human review</span>
                )}
                {f.judgeManipulation && (
                  <span className="text-[11px] px-2 py-[2px] rounded bg-warn/15 text-warn">judge manipulation</span>
                )}
              </div>
            }
          />
          <div className="space-y-3 text-sm">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              <div><span className="text-muted">Target</span><div className="text-text font-mono break-all mt-0.5">{f.target || "—"}</div></div>
              <div><span className="text-muted">Judge</span><div className="text-text mt-0.5">{f.judgeEngine || "—"}</div></div>
              <div><span className="text-muted">OWASP</span><div className="text-text mt-0.5">{f.owasp || "—"}</div></div>
              <div><span className="text-muted">Evidence</span><div className="text-text font-mono mt-0.5">{f.evidenceSha256}</div></div>
            </div>
            <div>
              <div className="text-xs text-muted mb-1">Verbatim evidence</div>
              <blockquote className="border-l-2 border-accent pl-3 py-1 bg-[#0D0D0F] rounded-r text-text font-mono text-xs max-h-32 overflow-y-auto">
                {f.quotedSpan}
              </blockquote>
            </div>
            <div>
              <div className="text-xs text-muted mb-1">Judge rationale</div>
              <div className="text-text text-xs">{f.judgeRationale}</div>
            </div>
            <div className="flex flex-wrap items-center gap-3 pt-1">
              {ACTIONS.map((a) => (
                <button
                  key={a.state}
                  disabled={busy === f.id}
                  onClick={() => dispose(f, a.state)}
                  className="px-3 py-1.5 rounded-lg border text-xs disabled:opacity-40 hover:bg-cardHover"
                  style={{ borderColor: `${a.color}66`, color: a.color }}
                >
                  {a.label}
                </button>
              ))}
              <Link
                href={`/runs/${f.runId}`}
                className="text-xs text-accent hover:underline ml-auto"
              >
                Open run →
              </Link>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
