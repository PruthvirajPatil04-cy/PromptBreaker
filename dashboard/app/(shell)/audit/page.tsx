"use client";
// Audit Log — every authenticated API call, newest first: who (role),
// what (method + path), and the HTTP outcome. Governance view for admins.
import { useCallback, useEffect, useState } from "react";
import { getAudit } from "@/lib/api";
import type { AuditEvent } from "@/lib/types";
import { Card, CardHeader } from "@/components/ui/primitives";

const ROLE_TONE: Record<string, string> = {
  admin: "text-accent", viewer: "text-amber-300", anonymous: "text-red-300",
};

function statusTone(status: number): string {
  if (status < 300) return "text-green-300";
  if (status < 500) return "text-amber-300";
  return "text-red-300";
}

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [role, setRole] = useState("");

  const load = useCallback(() => {
    getAudit(300)
      .then((e) => { setEvents(e); setError(null); })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 10_000);
    return () => clearInterval(t);
  }, [load]);

  const filtered = role ? events.filter((e) => e.role === role) : events;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Audit Log</h1>
          <div className="text-xs text-muted mt-1">
            {events.length} API call(s) recorded · refreshes every 10s
          </div>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="bg-bg border border-border rounded-lg px-3 py-2 text-sm"
          >
            <option value="">All roles</option>
            <option value="admin">admin</option>
            <option value="viewer">viewer</option>
            <option value="anonymous">anonymous</option>
          </select>
          <button
            onClick={load}
            className="px-4 py-2 rounded-lg bg-accent text-black text-sm font-medium hover:bg-accentHover"
          >
            Refresh
          </button>
        </div>
      </div>

      {error && <div className="text-red-300 font-mono text-sm">{error}</div>}

      <Card>
        <CardHeader
          title="API Activity"
          tooltip="RBAC: viewer keys can read and download reports; only admin keys can start scans, manage targets, or change suites."
        />
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-faint border-b border-border">
              <th className="pb-3 font-medium">TIME</th>
              <th className="pb-3 font-medium">ROLE</th>
              <th className="pb-3 font-medium">METHOD</th>
              <th className="pb-3 font-medium">PATH</th>
              <th className="pb-3 font-medium text-right">STATUS</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 100).map((e) => (
              <tr key={e.id} className="border-b border-border/50">
                <td className="py-2 text-muted whitespace-nowrap">{new Date(e.ts).toLocaleTimeString()}</td>
                <td className={`py-2 font-medium ${ROLE_TONE[e.role] ?? "text-fg"}`}>{e.role}</td>
                <td className="py-2 font-mono text-xs">{e.method}</td>
                <td className="py-2 font-mono text-xs text-muted">{e.path}</td>
                <td className={`py-2 text-right font-mono ${statusTone(e.status)}`}>{e.status}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={5} className="py-6 text-center text-faint text-xs">No audit events yet.</td></tr>
            )}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
