"use client";
// Hardening Wizard — the remediation loop end to end:
//   1. pick an open remediation → review the before/after system prompt
//   2. tune the hardened prompt
//   3. launch a re-scan with that prompt injected as the system context
//   4. watch it live, then auto-compare against the pre-hardening run
// The hardened prompt travels as `systemContext` on POST /v1/runs, where the
// engine wraps every probe with it — so the re-scan measures the ACTUAL fix.
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSuites, getTargets, startRun, ApiError } from "@/lib/api";
import { defaultExpiry, hostnameOf } from "@/components/StartScanModal";
import type { HardeningItem, SuiteInfo, TargetConfig } from "@/lib/types";

type Step = 1 | 2 | 3 | 4;

export function HardeningWizard({
  item, previousRunId, onClose,
}: {
  item: HardeningItem;
  previousRunId?: string;
  onClose: () => void;
}) {
  const router = useRouter();
  const [step, setStep] = useState<Step>(1);
  const [prompt, setPrompt] = useState(item.after);

  const [targets, setTargets] = useState<TargetConfig[]>([]);
  const [suites, setSuites] = useState<SuiteInfo[]>([]);
  const [targetId, setTargetId] = useState("");
  const [suite, setSuite] = useState("core");
  const [authorizedBy, setAuthorizedBy] = useState("");
  const [reference, setReference] = useState("");
  const [expires, setExpires] = useState(() => defaultExpiry());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [launched, setLaunched] = useState<{ runId: string } | null>(null);

  useEffect(() => {
    getTargets()
      .then((t) => { setTargets(t); if (t[0]) setTargetId(t[0].id); })
      .catch((e) => setError(String(e)));
    getSuites().then(setSuites).catch(() => {});
  }, []);

  const target = targets.find((t) => t.id === targetId);
  const canLaunch =
    !busy && !!target && prompt.trim().length > 0 &&
    authorizedBy.trim().length > 0 && reference.trim().length > 0;

  async function launch() {
    if (!target || !canLaunch) return;
    setBusy(true);
    setError(null);
    try {
      const { runId } = await startRun({
        target: target.endpoint,
        adapter: target.adapter,
        suite,
        allowPrivate: target.allowPrivate,
        apiKey: target.secretRef || undefined,
        systemContext: prompt,
        attestation: {
          targetPattern: hostnameOf(target.endpoint),
          authorizedBy: authorizedBy.trim(),
          reference: reference.trim(),
          expires: new Date(expires).toISOString(),
        },
      });
      setLaunched({ runId });
      setStep(4);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      setError(msg.includes("403") ? "Scope gate rejected: target outside authorized scope." : msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div
        className="w-full max-w-2xl rounded-xl border border-border bg-card p-6 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Hardening Wizard</h2>
            <div className="text-xs text-muted mt-0.5">{item.title}</div>
          </div>
          <button onClick={onClose} className="text-muted hover:text-text text-sm">✕</button>
        </div>

        {/* stepper */}
        <div className="flex items-center gap-2 text-xs">
          {["Review", "Tune prompt", "Re-scan", "Compare"].map((label, i) => {
            const n = (i + 1) as Step;
            const state = step === n ? "active" : step > n ? "done" : "todo";
            return (
              <div key={label} className="flex items-center gap-2">
                <span
                  className={`px-2 py-1 rounded ${
                    state === "active" ? "bg-accent/20 text-accent"
                    : state === "done" ? "text-pass" : "text-faint"
                  }`}
                >
                  {state === "done" ? "✓" : n}. {label}
                </span>
                {i < 3 && <span className="text-faint">→</span>}
              </div>
            );
          })}
        </div>

        {step === 1 && (
          <div className="space-y-3 text-sm">
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="bg-[#0D0D0F] border border-border rounded-lg p-3">
                <div className="text-muted mb-1">Before (current prompt)</div>
                <pre className="whitespace-pre-wrap font-mono text-[11px] text-fail/90">{item.before}</pre>
              </div>
              <div className="bg-[#0D0D0F] border border-border rounded-lg p-3">
                <div className="text-muted mb-1">After (proposed hardening)</div>
                <pre className="whitespace-pre-wrap font-mono text-[11px] text-pass/90">{item.after}</pre>
              </div>
            </div>
            <p className="text-xs text-muted">
              Step 2 lets you tune the hardened prompt, step 3 re-scans the target with it
              injected as the system context — the only honest test of a fix.
            </p>
            <div className="flex justify-end">
              <button
                onClick={() => { setPrompt(item.after); setStep(2); }}
                className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium hover:bg-accentHover"
              >
                Tune prompt →
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-3 text-sm">
            <div className="text-xs text-muted">Hardened system prompt (injected into every probe):</div>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={12}
              className="w-full bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-xs font-mono"
            />
            <div className="flex justify-between">
              <button
                onClick={() => setStep(1)}
                className="px-4 py-2 rounded-lg border border-border text-sm hover:bg-cardHover"
              >
                ← Back
              </button>
              <button
                onClick={() => prompt.trim() && setStep(3)}
                disabled={!prompt.trim()}
                className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium hover:bg-accentHover disabled:opacity-40"
              >
                Configure re-scan →
              </button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-3 text-sm">
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
            <div className="border-t border-border pt-3 space-y-3">
              <p className="text-xs text-muted">Scope attestation — required by the engine.</p>
              {([
                ["Authorized by", authorizedBy, setAuthorizedBy, "name / team"],
                ["Reference (ticket / engagement ID)", reference, setReference, "e.g. ENG-2026-014"],
              ] as [string, string, (v: string) => void, string][]).map(([label, val, set, ph]) => (
                <label key={label} className="block space-y-1.5">
                  <span className="text-xs text-muted">{label}</span>
                  <input
                    value={val}
                    onChange={(e) => set(e.target.value)}
                    placeholder={ph}
                    className="w-full bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-sm"
                  />
                </label>
              ))}
              <label className="block space-y-1.5">
                <span className="text-xs text-muted">Expires</span>
                <input
                  type="datetime-local"
                  value={expires}
                  onChange={(e) => setExpires(e.target.value)}
                  className="w-full bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-sm"
                />
              </label>
            </div>

            {error && (
              <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                {error}
              </div>
            )}

            <div className="flex justify-between">
              <button
                onClick={() => setStep(2)}
                className="px-4 py-2 rounded-lg border border-border text-sm hover:bg-cardHover"
              >
                ← Back
              </button>
              <button
                onClick={launch}
                disabled={!canLaunch}
                className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium hover:bg-accentHover disabled:opacity-40"
              >
                {busy ? "Starting…" : "Launch hardened re-scan"}
              </button>
            </div>
          </div>
        )}

        {step === 4 && launched && (
          <div className="space-y-4 text-sm">
            <div className="rounded-lg border border-pass/40 bg-pass/10 px-4 py-3 text-pass">
              ✓ Hardened re-scan queued — the engine wrapped every probe with your prompt.
            </div>
            <div className="text-xs text-muted font-mono break-all">{launched.runId}</div>
            <div className="flex flex-wrap gap-3">
              <button
                onClick={() => router.push(`/runs/${launched.runId}`)}
                className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium hover:bg-accentHover"
              >
                Watch live run →
              </button>
              {previousRunId && (
                <button
                  onClick={() => router.push(`/compare?a=${previousRunId}&b=${launched.runId}`)}
                  className="px-4 py-2 rounded-lg border border-border text-sm hover:bg-cardHover"
                >
                  Compare before / after →
                </button>
              )}
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-lg border border-border text-sm text-muted hover:bg-cardHover"
              >
                Close
              </button>
            </div>
            <p className="text-xs text-faint">
              {previousRunId
                ? "Compare shows the score delta between the pre-hardening run and this one."
                : "No prior run found to compare against — run a baseline scan first."}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
