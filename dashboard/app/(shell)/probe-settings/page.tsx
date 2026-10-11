"use client";
// Probe Settings — suite/probe registry with enable toggles and weights.
import { useEffect, useState } from "react";
import { getProbeRegistry } from "@/lib/api";
import type { ProbeRegistryItem } from "@/lib/types";
import { Card, CardHeader, SeverityPill } from "@/components/ui/primitives";

export default function ProbeSettingsPage() {
  const [items, setItems] = useState<ProbeRegistryItem[]>([]);
  useEffect(() => { getProbeRegistry().then(setItems); }, []);

  const toggle = (id: string) =>
    setItems((prev) => prev.map((p) => (p.id === id ? { ...p, enabled: !p.enabled } : p)));
  const setWeight = (id: string, w: number) =>
    setItems((prev) => prev.map((p) => (p.id === id ? { ...p, weight: w } : p)));

  const enabled = items.filter((p) => p.enabled).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Probe Settings</h1>
          <div className="text-xs text-muted mt-1">{enabled} of {items.length} probes enabled</div>
        </div>
        <button className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium hover:bg-accentHover">
          New Custom Probe
        </button>
      </div>

      <Card>
        <CardHeader title="Probe Registry" tooltip="Weights feed the scoring model. Disabled probes are excluded from runs." />
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-faint border-b border-border">
              <th className="pb-3 font-medium">ENABLED</th>
              <th className="pb-3 font-medium">ID</th>
              <th className="pb-3 font-medium">NAME</th>
              <th className="pb-3 font-medium">CATEGORY</th>
              <th className="pb-3 font-medium">OWASP</th>
              <th className="pb-3 font-medium">SEVERITY</th>
              <th className="pb-3 font-medium">WEIGHT</th>
            </tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.id} className="border-b border-border/50">
                <td className="py-3">
                  <button
                    onClick={() => toggle(p.id)}
                    className={`h-5 w-9 rounded-full transition-colors relative ${p.enabled ? "bg-accent" : "bg-[#2A2A30]"}`}
                  >
                    <span
                      className="absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all"
                      style={{ left: p.enabled ? 18 : 2 }}
                    />
                  </button>
                </td>
                <td className="py-3 font-mono text-xs text-muted">{p.id}</td>
                <td className="py-3 text-text">{p.name}</td>
                <td className="py-3 text-muted">{p.category}</td>
                <td className="py-3 text-muted">{p.owasp}</td>
                <td className="py-3"><SeverityPill severity={p.severity} /></td>
                <td className="py-3">
                  <input
                    type="number" min={0} max={5} step={0.5} value={p.weight}
                    onChange={(e) => setWeight(p.id, Number(e.target.value))}
                    className="w-16 bg-[#0D0D0F] border border-border rounded px-2 py-1 text-xs tabular-nums outline-none focus:border-accent"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
