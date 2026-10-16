"use client";
// Start Scan modal — target + suite + mandatory scope attestation.
// The engine refuses to run without a valid attestation (is_valid checks
// pattern/authorization/expiry), so this form is the dashboard's half of
// that gate: no attestation fields filled → no run created.
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getTargets, startRun, ApiError } from "@/lib/api";
import type { TargetConfig } from "@/lib/types";

const SUITES = ["core"];

export function StartScanModal({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [targets, setTargets] = useState<TargetConfig[]>([]);
  const [targetId, setTargetId] = useState("");
  const [suite, setSuite] = useState("core");
  const [authorizedBy, setAuthorizedBy] = useState("");
  const [reference, setReference] = useState("");
  const [expires, setExpires] = useState(() => defaultExpiry());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getTargets()
      .then((t) => {
        setTargets(t);
        if (t.length > 0) setTargetId(t[0].id);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const target = targets.find((t) => t.id === targetId);
  const canSubmit =
    !busy && !!target && authorizedBy.trim().length > 0 &&
    reference.trim().length > 0 && expires.length > 0;

  async function submit() {
    if (!target || !canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      const host = hostnameOf(target.endpoint);
      const { runId } = await startRun({
        target: target.endpoint,
        adapter: target.adapter,
        suite,
        allowPrivate: target.allowPrivate,
        apiKey: target.secretRef || undefined,
        attestation: {
          targetPattern: host,
          authorizedBy: authorizedBy.trim(),
          reference: reference.trim(),
          expires: new Date(expires).toISOString(),
        },
      });
      router.push(`/runs/${runId}`);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      setError(msg.includes("403") ? "Scope gate rejected: target outside authorized scope." : msg);
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-xl border border-border bg-card p-6 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">New Test Run</h2>
          <button onClick={onClose} className="text-muted hover:text-text text-sm">✕</button>
        </div>

        <Field label="Target">
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
          {target && (
            <p className="text-xs text-faint mt-1 font-mono break-all">{target.endpoint}</p>
          )}
        </Field>

        <Field label="Suite">
          <select
            value={suite}
            onChange={(e) => setSuite(e.target.value)}
            className="w-full bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-sm"
          >
            {SUITES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>

        <div className="border-t border-border pt-3 space-y-3">
          <p className="text-xs text-muted">
            Scope attestation — required. The engine rejects runs without it.
          </p>
          <Field label="Authorized by">
            <input
              value={authorizedBy}
              onChange={(e) => setAuthorizedBy(e.target.value)}
              placeholder="name / team"
              className="w-full bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-sm"
            />
          </Field>
          <Field label="Reference (ticket / engagement ID)">
            <input
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              placeholder="e.g. ENG-2026-014"
              className="w-full bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-sm"
            />
          </Field>
          <Field label="Expires">
            <input
              type="datetime-local"
              value={expires}
              onChange={(e) => setExpires(e.target.value)}
              className="w-full bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-sm"
            />
          </Field>
        </div>

        {error && (
          <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-300">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-1">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-border text-sm text-text hover:bg-cardHover"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={!canSubmit}
            className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium hover:bg-accentHover disabled:opacity-40"
          >
            {busy ? "Starting…" : "Start Scan"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs text-muted">{label}</span>
      {children}
    </label>
  );
}

function hostnameOf(endpoint: string): string {
  try {
    return new URL(endpoint).hostname;
  } catch {
    return endpoint.replace(/^https?:\/\//, "").split("/")[0] ?? endpoint;
  }
}

function defaultExpiry(): string {
  const d = new Date(Date.now() + 24 * 3600 * 1000);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}
