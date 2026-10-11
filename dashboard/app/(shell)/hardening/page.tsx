"use client";
// Prompt Hardening — remediation queue: finding → suggested system-prompt patch.
import { useEffect, useState } from "react";
import { getHardening } from "@/lib/api";
import type { HardeningItem } from "@/lib/types";
import { Card, CardHeader, SeverityPill } from "@/components/ui/primitives";

export default function HardeningPage() {
  const [items, setItems] = useState<HardeningItem[]>([]);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => { getHardening().then(setItems); }, []);

  const setStatus = (id: string, status: HardeningItem["status"]) =>
    setItems((prev) => prev.map((h) => (h.id === id ? { ...h, status } : h)));

  const copy = (h: HardeningItem) => {
    navigator.clipboard?.writeText(h.after).catch(() => {});
    setCopied(h.id);
    setTimeout(() => setCopied(null), 1200);
  };

  const open = items.filter((h) => h.status === "open");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Prompt Hardening</h1>
          <div className="text-xs text-muted mt-1">{open.length} open remediation{open.length === 1 ? "" : "s"}</div>
        </div>
      </div>

      {items.map((h) => (
        <Card key={h.id}>
          <CardHeader
            title={h.title}
            tooltip={`Linked finding: ${h.findingId}`}
            right={
              <div className="flex items-center gap-3">
                <SeverityPill severity={h.severity} />
                <span
                  className="text-[11px] font-medium"
                  style={{ color: h.status === "accepted" ? "#22C55E" : h.status === "dismissed" ? "#8B8D93" : "#F59E0B" }}
                >
                  {h.status.toUpperCase()}
                </span>
              </div>
            }
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-xs text-muted mb-1">Before</div>
              <pre className="bg-[#0D0D0F] border border-border rounded-lg p-3 text-xs text-muted whitespace-pre-wrap font-mono">
                {h.before}
              </pre>
            </div>
            <div>
              <div className="text-xs text-muted mb-1">After (suggested)</div>
              <pre className="bg-[#0D0D0F] border border-accent/30 rounded-lg p-3 text-xs text-text whitespace-pre-wrap font-mono">
                {h.after}
              </pre>
            </div>
          </div>
          <div className="mt-3 flex gap-3">
            <button
              onClick={() => copy(h)}
              className="px-3 py-1.5 rounded-lg border border-border text-xs hover:bg-cardHover"
            >
              {copied === h.id ? "Copied ✓" : "Copy patch"}
            </button>
            <button
              onClick={() => setStatus(h.id, "accepted")}
              className="px-3 py-1.5 rounded-lg bg-accent/15 text-accent text-xs"
            >
              Accept
            </button>
            <button
              onClick={() => setStatus(h.id, "dismissed")}
              className="px-3 py-1.5 rounded-lg border border-border text-xs text-muted hover:bg-cardHover"
            >
              Dismiss
            </button>
          </div>
        </Card>
      ))}
    </div>
  );
}
