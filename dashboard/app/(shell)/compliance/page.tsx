"use client";
// Compliance — OWASP LLM Top 10 + NIST AI RMF control matrix.
import { useEffect, useState } from "react";
import { getCompliance } from "@/lib/api";
import type { ComplianceControl } from "@/lib/types";
import { Card, CardHeader } from "@/components/ui/primitives";

const STATUS_STYLE: Record<string, { fg: string; label: string }> = {
  pass: { fg: "#22C55E", label: "Covered" },
  partial: { fg: "#F59E0B", label: "Partial" },
  gap: { fg: "#EF4444", label: "Gap" },
};

export default function CompliancePage() {
  const [controls, setControls] = useState<ComplianceControl[]>([]);
  useEffect(() => { getCompliance().then(setControls); }, []);

  const frameworks = Array.from(new Set(controls.map((c) => c.framework)));
  const overall = controls.length
    ? Math.round(controls.reduce((s, c) => s + c.coveragePct, 0) / controls.length)
    : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Compliance</h1>
          <div className="text-xs text-muted mt-1">Overall coverage {overall}%</div>
        </div>
        <button className="px-4 py-2 rounded-lg border border-border text-sm hover:bg-cardHover">
          Export Evidence Pack
        </button>
      </div>

      {frameworks.map((fw) => (
        <Card key={fw}>
          <CardHeader title={fw === "OWASP-LLM" ? "OWASP LLM Top 10" : "NIST AI RMF"} />
          <div className="space-y-3">
            {controls.filter((c) => c.framework === fw).map((c) => {
              const style = STATUS_STYLE[c.status];
              return (
                <div key={c.id} className="flex items-center gap-4">
                  <div className="w-24 shrink-0 font-mono text-xs text-muted">{c.id}</div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-text">{c.title}</div>
                    <div className="h-2 rounded-full bg-[#1F1F23] mt-1.5 overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${c.coveragePct}%`, background: style.fg }} />
                    </div>
                  </div>
                  <div className="w-16 text-right text-xs tabular-nums" style={{ color: style.fg }}>
                    {c.coveragePct}%
                  </div>
                  <div className="w-20 text-right">
                    <span className="text-[11px] font-medium" style={{ color: style.fg }}>{style.label}</span>
                  </div>
                  <div className="w-24 text-right text-xs text-muted">
                    {c.linkedFindingIds.length > 0 ? `${c.linkedFindingIds.length} findings` : "—"}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      ))}
    </div>
  );
}
