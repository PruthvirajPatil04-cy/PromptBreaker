"use client";
// Target Settings — adapter config. Secrets shown as references, never plaintext.
// "Test connection" performs a REAL pre-stage health check against the engine
// (POST /v1/targets/{id}/verify): one harmless round-trip, never a probe —
// this is the pre-demo gate that catches dead endpoints before going on stage.
import { useEffect, useState } from "react";
import { getTargets, verifyTarget } from "@/lib/api";
import type { TargetConfig, VerifyTargetResult } from "@/lib/types";
import { Card, CardHeader } from "@/components/ui/primitives";

export default function TargetSettingsPage() {
  const [targets, setTargets] = useState<TargetConfig[]>([]);
  const [testing, setTesting] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, VerifyTargetResult>>({});

  useEffect(() => { getTargets().then(setTargets).catch(() => {}); }, []);

  const testConnection = async (id: string) => {
    setTesting(id);
    try {
      const r = await verifyTarget(id);
      setResults((prev) => ({ ...prev, [id]: r }));
      setTargets((prev) => prev.map((t) => (t.id === id ? { ...t, verified: r.verified } : t)));
    } catch (e) {
      setResults((prev) => ({
        ...prev,
        [id]: { targetId: id, verified: false, latencyMs: 0, detail: String(e) },
      }));
    } finally {
      setTesting(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Target Settings</h1>
          <div className="text-xs text-muted mt-1">
            Test connection runs a real health check — one harmless round-trip, no probes fired.
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {targets.map((t) => (
          <Card key={t.id}>
            <CardHeader
              title={t.name}
              right={
                <span className="inline-flex items-center gap-1.5 text-xs text-muted">
                  {t.verified ? "verified" : "unverified"}
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: t.verified ? "#22C55E" : "#F59E0B" }} />
                </span>
              }
            />
            <div className="space-y-3 text-sm">
              {([
                ["Adapter", t.adapter],
                ["Endpoint", t.endpoint],
                ["Secret reference", t.secretRef || "(none — unauthenticated)"],
                ["Egress", t.allowPrivate ? "private allowed (lab)" : "public only"],
                ["Max redirects", String(t.maxRedirects)],
                ["Sandbox", t.sandbox ? "gVisor isolated" : "host network"],
              ] as [string, string][]).map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4">
                  <span className="text-muted shrink-0">{k}</span>
                  <span className={`text-right ${k === "Endpoint" || k === "Secret reference" ? "font-mono text-xs break-all" : "text-text"}`}>
                    {v}
                  </span>
                </div>
              ))}
            </div>
            <div className="mt-4 flex gap-3 items-center">
              <button
                onClick={() => testConnection(t.id)}
                disabled={testing === t.id}
                className="px-3 py-1.5 rounded-lg border border-border text-xs hover:bg-cardHover disabled:opacity-50"
              >
                {testing === t.id ? "Checking…" : "Test connection"}
              </button>
              <button className="px-3 py-1.5 rounded-lg border border-border text-xs hover:bg-cardHover">Edit</button>
              {results[t.id] && (
                <span
                  className="text-[11px] font-mono truncate max-w-[16rem]"
                  title={results[t.id].detail}
                  style={{ color: results[t.id].verified ? "#22C55E" : "#EF4444" }}
                >
                  {results[t.id].verified
                    ? `✓ ${results[t.id].latencyMs}ms — ${results[t.id].detail}`
                    : `✗ ${results[t.id].detail}`}
                </span>
              )}
            </div>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader title="SSRF Egress Guard" tooltip="All adapter requests pass this guard. Private ranges are blocked unless a target is explicitly marked as a lab." />
        <ul className="text-sm text-muted space-y-1.5">
          <li>• http/https schemes only</li>
          <li>• DNS resolved first, then pinned — defeats rebinding</li>
          <li>• Blocks loopback, link-local (169.254.x.x incl. cloud metadata), private, CGNAT, multicast, reserved</li>
          <li>• Redirects followed manually, each hop re-validated, capped</li>
        </ul>
      </Card>
    </div>
  );
}
