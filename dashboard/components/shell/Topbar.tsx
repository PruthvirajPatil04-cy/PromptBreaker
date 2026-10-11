"use client";
// Topbar: project/target switcher breadcrumb + avatar.
import { useState } from "react";
import { getProjects } from "@/lib/api";

export function Topbar() {
  const projects = getProjects();
  const [project, setProject] = useState(projects[0].name);
  const [target] = useState("Car Sales");

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
      <div className="h-9 w-9 rounded-full bg-[#F5C9A5]" />
    </header>
  );
}
