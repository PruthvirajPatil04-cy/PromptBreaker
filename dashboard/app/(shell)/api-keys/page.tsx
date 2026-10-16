"use client";
// API Keys (C1) — issue and revoke RBAC keys for CI and teammates.
// Only sha256 is stored server-side: the plaintext is displayed EXACTLY once
// at creation. viewer keys are read-only; admin keys can mutate. Revocation
// takes effect immediately (the engine clears its key cache on delete).
import { useCallback, useEffect, useState } from "react";
import { createKey, getKeys, revokeKey } from "@/lib/api";
import type { ApiKey, CreatedApiKey } from "@/lib/types";
import { Card, CardHeader } from "@/components/ui/primitives";

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [role, setRole] = useState<"admin" | "viewer">("viewer");
  const [busy, setBusy] = useState(false);
  const [fresh, setFresh] = useState<CreatedApiKey | null>(null);
  const [copied, setCopied] = useState(false);
  const [revoking, setRevoking] = useState<string | null>(null);

  const load = useCallback(() => {
    getKeys().then((k) => { setKeys(k); setError(null); })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => { load(); }, [load]);

  const issue = async () => {
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createKey({ name: name.trim(), role });
      setFresh(created);
      setName("");
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (id: string) => {
    setRevoking(id);
    try {
      await revokeKey(id);
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setRevoking(null);
    }
  };

  const copyFresh = () => {
    if (!fresh) return;
    navigator.clipboard?.writeText(fresh.key).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">API Keys</h1>
        <div className="text-xs text-muted mt-1">
          RBAC keys for CI jobs and teammates. Hash-only storage — the plaintext is shown once.
        </div>
      </div>

      {error && (
        <div className="border border-red-500/40 bg-red-500/10 rounded-lg px-4 py-3 text-sm text-red-200 font-mono break-all">
          {error}
        </div>
      )}

      {fresh && (
        <div className="border border-amber-500/40 bg-amber-500/10 rounded-xl p-4 space-y-2">
          <div className="text-sm text-amber-200 font-semibold">
            Key issued — copy it now. It cannot be shown again.
          </div>
          <div className="flex items-center gap-3">
            <code className="flex-1 bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-xs font-mono break-all">
              {fresh.key}
            </code>
            <button
              onClick={copyFresh}
              className="px-3 py-2 rounded-lg bg-accent text-black text-xs font-medium hover:bg-accentHover shrink-0"
            >
              {copied ? "Copied ✓" : "Copy"}
            </button>
            <button
              onClick={() => setFresh(null)}
              className="px-3 py-2 rounded-lg border border-border text-xs text-muted hover:bg-cardHover shrink-0"
            >
              Dismiss
            </button>
          </div>
          <div className="text-xs text-muted">
            {fresh.role === "admin"
              ? "admin — full read/write, can start runs and manage keys."
              : "viewer — read-only; write endpoints return 403."}
          </div>
        </div>
      )}

      <Card>
        <CardHeader title="Issue a key" />
        <div className="flex flex-wrap items-end gap-3">
          <label className="block space-y-1.5 flex-1 min-w-[14rem]">
            <span className="text-xs text-muted">Name (what is this key for?)</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. github-actions-ci"
              className="w-full bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-sm"
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs text-muted">Role</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as "admin" | "viewer")}
              className="bg-[#0D0D0F] border border-border rounded-lg px-3 py-2 text-sm"
            >
              <option value="viewer">viewer — read only</option>
              <option value="admin">admin — read/write</option>
            </select>
          </label>
          <button
            onClick={issue}
            disabled={!name.trim() || busy}
            className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium hover:bg-accentHover disabled:opacity-40"
          >
            {busy ? "Issuing…" : "Issue key"}
          </button>
        </div>
      </Card>

      <Card>
        <CardHeader
          title={`Issued keys (${keys.length})`}
          right={<span className="text-xs text-muted">env-configured keys live in .env and are not listed</span>}
        />
        {keys.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted">
            No dashboard keys issued yet. Issue one for your CI pipeline or teammate.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-faint border-b border-border">
                <th className="pb-2 font-medium">NAME</th>
                <th className="pb-2 font-medium">PREFIX</th>
                <th className="pb-2 font-medium">ROLE</th>
                <th className="pb-2 font-medium">CREATED</th>
                <th className="pb-2 font-medium">STATUS</th>
                <th className="pb-2" />
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id} className="border-b border-border/50">
                  <td className="py-3 text-text">{k.name}</td>
                  <td className="py-3 font-mono text-xs text-muted">{k.prefix}…</td>
                  <td className="py-3">
                    <span
                      className="text-xs px-2 py-[2px] rounded"
                      style={{
                        color: k.role === "admin" ? "#F59E0B" : "#60A5FA",
                        background: k.role === "admin" ? "rgba(245,158,11,.12)" : "rgba(96,165,250,.12)",
                      }}
                    >
                      {k.role}
                    </span>
                  </td>
                  <td className="py-3 text-muted tabular-nums text-xs">
                    {k.createdAt ? k.createdAt.slice(0, 10) : "—"}
                  </td>
                  <td className="py-3 text-xs" style={{ color: k.revoked ? "#8B8D93" : "#22C55E" }}>
                    {k.revoked ? "revoked" : "active"}
                  </td>
                  <td className="py-3 text-right">
                    {!k.revoked && (
                      <button
                        onClick={() => revoke(k.id)}
                        disabled={revoking === k.id}
                        className="px-3 py-1.5 rounded-lg border border-red-500/40 text-xs text-red-300 hover:bg-red-500/10 disabled:opacity-40"
                      >
                        {revoking === k.id ? "Revoking…" : "Revoke"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
