"use client";
// Topbar: project/target switcher breadcrumb + engine health badge + avatar.
import { useEffect, useState } from "react";
import { getProjects, health, USE_MOCK } from "@/lib/api";

export function Topbar() {
  const projects = getProjects();
  const [project, setProject] = useState(projects[0].name);
  const [target] = useState("Car Sales");
  const [status, setStatus] = useState<"checking" | "up" | "down">("checking");
  const [version, setVersion] = useState("");

  useEffect(() => {
    if (USE_MOCK) return;
    let alive = true;
    const probe = () =>
      health()
        .then((h) => {
          if (!alive) return;
          setStatus(h.ok ? "up" : "down");
          setVersion(h.version);
        })
        .catch(() => alive && setStatus("down"));
    probe();
    const t = setInterval(probe, 15000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const dot =
    status === "up" ? "#22C55E" : status === "down" ? "#EF4444" : "#8B8D93";

  return (
    <header className="h-14 shrink-0 border-b border-border flex items-center justify-between px-6 bg-bg">
      <div className="flex items-center gap-2 text-sm">
        <select
          value={project}
          onChange={(e) => setProject(e.target.value)}
          className="bg-card border border-border rounded-lg px-3 py-1.5 text-text text-sm outline-none focus:border-accent"
        >
          {projects.map((p) => (
            <option key={p.id} value={p.name}>{p.name}</option>
          ))}
        </select>
        <span className="text-faint">/</span>
        <span className="px-3 py-1.5 rounded-lg bg-card border border-border text-text">{target}</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-muted">
          <path d="M8 9l4-4 4 4M8 15l4 4 4-4" />
        </svg>
      </div>
      <div className="flex items-center gap-4">
        {!USE_MOCK && (
          <span
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-border bg-card text-xs text-muted"
            title={version ? `engine v${version}` : "engine health"}
          >
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: dot }} />
            {status === "checking" ? "checking…" : status === "up" ? "engine online" : "engine offline"}
          </span>
        )}
        <div className="h-9 w-9 rounded-full bg-[#F5C9A5]" />
      </div>
    </header>
  );
}
