"use client";
// Probe Settings — suite/probe registry with enable toggles and weights,
// plus custom suite upload (probes as JSON: your own objects and/or core ids).
import { useCallback, useEffect, useState } from "react";
import { createSuite, deleteSuite, getProbeRegistry, getSuites } from "@/lib/api";
import type { ProbeRegistryItem, SuiteInfo } from "@/lib/types";
import { Card, CardHeader, SeverityPill } from "@/components/ui/primitives";

function CustomSuites() {
  const [suites, setSuites] = useState<SuiteInfo[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [probesJson, setProbesJson] = useState("[]");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => { getSuites().then(setSuites).catch(() => {}); }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const submit = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const probes = JSON.parse(probesJson) as unknown;
      if (!Array.isArray(probes)) throw new Error("probes must be a JSON array");
      const created = await createSuite({ name, description, probes: probes as (Record<string, unknown> | string)[] });
      setMsg({ ok: true, text: `Suite “${created.name}” uploaded — ${created.probes} probe(s). Selectable in Start Scan now.` });
      setName(""); setDescription(""); setProbesJson("[]");
      refresh();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  };

  const remove = async (n: string) => {
    setMsg(null);
    try {
      await deleteSuite(n);
      setMsg({ ok: true, text: `Deleted suite “${n}”.` });
      refresh();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
    }
  };

  return (
    <div className="grid lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader
          title="Import Custom Suite"
          tooltip='JSON array of probes: full probe objects {"id","name","category","payload",...} and/or core ids "PI-001".'
        />
        <div className="space-y-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="suite name (a-z, 0-9, hyphen)"
            className="w-full bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent"
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="one-line description"
            className="w-full bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent"
          />
          <textarea
            value={probesJson}
            onChange={(e) => setProbesJson(e.target.value)}
            rows={8}
            spellCheck={false}
            placeholder='[{"id":"X-001","name":"Custom ask","category":"prompt_injection","payload":"..."},"PI-002"]'
            className="w-full bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-xs font-mono outline-none focus:border-accent"
          />
          <div className="flex items-center gap-3">
            <button
              onClick={submit}
              disabled={busy || !name || probesJson.trim() === "[]"}
              className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium hover:bg-accentHover disabled:opacity-40"
            >
              {busy ? "Uploading…" : "Upload Suite"}
            </button>
            {msg && (
              <span className={`text-xs ${msg.ok ? "text-green-300" : "text-red-300"}`}>{msg.text}</span>
            )}
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Suite Library" tooltip="Shipped suites are protected; custom suites can be deleted here." />
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-faint border-b border-border">
              <th className="pb-3 font-medium">SUITE</th>
              <th className="pb-3 font-medium">PROBES</th>
              <th className="pb-3 font-medium">KIND</th>
              <th className="pb-3 font-medium">DESCRIPTION</th>
              <th className="pb-3"></th>
            </tr>
          </thead>
          <tbody>
            {suites.map((s) => (
              <tr key={s.name} className="border-b border-border/50">
                <td className="py-2.5 font-mono text-xs text-accent">{s.name}</td>
                <td className="py-2.5 tabular-nums">{s.probes}</td>
                <td className="py-2.5">
                  <span className={`text-[10px] tracking-wider font-semibold px-2 py-0.5 rounded border ${
                    s.builtin ? "border-border text-faint" : "border-accent/50 text-accent"}`}>
                    {s.builtin ? "SHIPPED" : "CUSTOM"}
                  </span>
                </td>
                <td className="py-2.5 text-xs text-muted">{s.description}</td>
                <td className="py-2.5 text-right">
                  {!s.builtin && (
                    <button
                      onClick={() => remove(s.name)}
                      className="text-xs text-red-300 hover:text-red-200"
                    >
                      delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {suites.length === 0 && (
              <tr><td colSpan={5} className="py-5 text-center text-xs text-faint">Loading suites…</td></tr>
            )}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

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

      <CustomSuites />
    </div>
  );
}
