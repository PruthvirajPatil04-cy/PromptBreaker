"use client";
// Target Settings — adapter config. Secrets shown as references, never plaintext.
import { useEffect, useState } from "react";
import { getTargets } from "@/lib/api";
import type { TargetConfig } from "@/lib/types";
import { Card, CardHeader, StatusPill } from "@/components/ui/primitives";

export default function TargetSettingsPage() {
  const [targets, setTargets] = useState<TargetConfig[]>([]);
  const [testing, setTesting] = useState<string | null>(null);

  useEffect(() => { getTargets().then(setTargets); }, []);

  const testConnection = (id: string) => {
    setTesting(id);
    setTimeout(() => setTesting(null), 900);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Target Settings</h1>
        <button className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium hover:bg-accentHover">
          Add Target +
        </button>
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
            <div className="mt-4 flex gap-3">
              <button
                onClick={() => testConnection(t.id)}
                disabled={testing === t.id}
                className="px-3 py-1.5 rounded-lg border border-border text-xs hover:bg-cardHover disabled:opacity-50"
              >
                {testing === t.id ? "Testing…" : "Test connection"}
              </button>
              <button className="px-3 py-1.5 rounded-lg border border-border text-xs hover:bg-cardHover">Edit</button>
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
