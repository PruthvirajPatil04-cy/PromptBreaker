"use client";
// Scheduled Scans (C3) — recurring runs fired by the engine's in-process
// scheduler. Each schedule carries its OWN scope attestation; when it expires,
// firing stops (lastError explains why) until the schedule is recreated —
// the legal gate applies to automation exactly as it does to manual runs.
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  createSchedule, deleteSchedule, getSchedules, getSuites, getTargets, setScheduleEnabled,
} from "@/lib/api";
import { defaultExpiry, hostnameOf } from "@/components/StartScanModal";
import type { Schedule, SuiteInfo, TargetConfig } from "@/lib/types";
import { Card, CardHeader } from "@/components/ui/primitives";

export default function SchedulesPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [targets, setTargets] = useState<TargetConfig[]>([]);
  const [suites, setSuites] = useState<SuiteInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // creation form
  const [name, setName] = useState("");
  const [targetId, setTargetId] = useState("");
  const [suite, setSuite] = useState("core");
  const [interval, setInterval] = useState(60);
  const [authorizedBy, setAuthorizedBy] = useState("");
  const [reference, setReference] = useState("");
  const [expires, setExpires] = useState(() => defaultExpiry());

  const load = useCallback(() => {
    getSchedules().then((s) => { setSchedules(s); setError(null); })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    load();
    getTargets().then((t) => { setTargets(t); if (t[0]) setTargetId(t[0].id); }).catch(() => {});
    getSuites().then(setSuites).catch(() => {});
  }, [load]);

  const target = targets.find((t) => t.id === targetId);
  const canCreate =
    !busy && !!target && name.trim().length > 0 &&
    authorizedBy.trim().length > 0 && reference.trim().length > 0 && interval >= 1;

  const create = async () => {
    if (!target || !canCreate) return;
    setBusy(true);
    setError(null);
    try {
      await createSchedule({
        name: name.trim(),
        targetId,
        suite,
        intervalMinutes: interval,
        attestation: {
          targetPattern: hostnameOf(target.endpoint),
          authorizedBy: authorizedBy.trim(),
          reference: reference.trim(),
          expires: new Date(expires).toISOString(),
        },
      });
      setName("");
      setAuthorizedBy("");
      setReference("");
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const toggle = async (s: Schedule) => {
    setSchedules((prev) => prev.map((x) => (x.id === s.id ? { ...x, enabled: !x.enabled } : x)));
    try {
      await setScheduleEnabled(s.id, !s.enabled);
    } catch (e) {
      setError(String(e));
      load();
    }
  };

  const remove = async (id: string) => {
    try {
      await deleteSchedule(id);
      setSchedules((prev) => prev.filter((s) => s.id !== id));
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Scheduled Scans</h1>
        <div className="text-xs text-muted mt-1">
          The engine fires due schedules every 15s. Each schedule attests its own scope —
          expired attestation stops firing until recreated.
        </div>
      </div>

      {error && (
        <div className="border border-red-500/40 bg-red-500/10 rounded-lg px-4 py-3 text-sm text-red-200 font-mono break-all">
          {error}
        </div>
      )}

      <Card>
        <CardHeader title={`Schedules (${schedules.length})`} />
        {schedules.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted">
            No schedules yet — create the first recurring scan below.
          </div>
        ) : (
          <div className="space-y-3">
            {schedules.map((s) => (
              <div key={s.id} className="border border-border rounded-xl px-4 py-3 flex flex-wrap items-center gap-4">
                <div className="flex-1 min-w-[12rem]">
                  <div className="text-sm text-text font-medium">{s.name}</div>
                  <div className="text-xs text-muted font-mono mt-0.5">
                    {s.suite} · every {s.intervalMinutes}m · target {s.targetId}
                  </div>
                </div>
                <div className="text-xs text-muted">
                  <div>next: {s.nextRunAt ? s.nextRunAt.slice(0, 16).replace("T", " ") : "—"}</div>
                  <div className="font-mono">
                    last: {s.lastRunId ? (
                      <Link href={`/runs/${s.lastRunId}`} className="text-accent hover:underline">
                        {s.lastRunId.slice(0, 12)}…
                      </Link>
                    ) : "never"}
                  </div>
                </div>
                {s.lastError && (
                  <div className="text-xs text-warn max-w-[16rem]" title={s.lastError}>
                    ⚠ {s.lastError}
                  </div>
                )}
                <div className="flex items-center gap-2 ml-auto">
                  <button
                    onClick={() => toggle(s)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
                      s.enabled ? "bg-pass/15 text-pass" : "bg-cardHover text-muted"
                    }`}
                  >
                    {s.enabled ? "Enabled" : "Paused"}
                  </button>
                  <button
                    onClick={() => remove(s.id)}
                    className="px-3 py-1.5 rounded-lg border border-red-500/40 text-xs text-red-300 hover:bg-red-500/10"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="New schedule" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <label className="block space-y-1.5">
            <span className="text-xs text-muted">Name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. nightly regression"
              className="w-full bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-sm"
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs text-muted">Interval (minutes)</span>
            <input
              type="number"
              min={1}
              value={interval}
              onChange={(e) => setInterval(Math.max(1, Number(e.target.value) || 1))}
              className="w-full bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-sm"
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs text-muted">Target</span>
            <select
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              className="w-full bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-sm"
            >
              {targets.length === 0 && <option value="">No targets configured</option>}
              {targets.map((t) => (
                <option key={t.id} value={t.id}>{t.name} — {t.adapter}</option>
              ))}
            </select>
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs text-muted">Suite</span>
            <select
              value={suite}
              onChange={(e) => setSuite(e.target.value)}
              className="w-full bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-sm"
            >
              {(suites.length ? suites : [{ name: "core", probes: 12, description: "", builtin: true }]).map((s) => (
                <option key={s.name} value={s.name}>{s.name} — {s.probes} probes</option>
              ))}
            </select>
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs text-muted">Authorized by</span>
            <input
              value={authorizedBy}
              onChange={(e) => setAuthorizedBy(e.target.value)}
              placeholder="name / team"
              className="w-full bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-sm"
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs text-muted">Reference (ticket / engagement ID)</span>
            <input
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              placeholder="e.g. ENG-2026-014"
              className="w-full bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-sm"
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs text-muted">Attestation expires</span>
            <input
              type="datetime-local"
              value={expires}
              onChange={(e) => setExpires(e.target.value)}
              className="w-full bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-sm"
            />
          </label>
          <div className="flex items-end">
            <button
              onClick={create}
              disabled={!canCreate}
              className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium hover:bg-accentHover disabled:opacity-40"
            >
              {busy ? "Creating…" : "Create schedule"}
            </button>
          </div>
        </div>
      </Card>
    </div>
  );
}
