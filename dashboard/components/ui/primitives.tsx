// Small domain UI primitives shared across pages.
import type { ReactNode } from "react";
import { scoreColor } from "@/lib/scoring";

export function ScoreBadge({ score }: { score: number }) {
  const c = scoreColor(score);
  return (
    <span
      className="text-xs font-semibold tabular-nums px-2 py-[2px] rounded"
      style={{ color: c, background: `${c}1A` }}
    >
      {score.toFixed(2)}
    </span>
  );
}

export function StatusPill({ status }: { status: string }) {
  const color = status === "FINISHED" ? "#22C55E" : status === "RUNNING" ? "#14B8A6" : "#F59E0B";
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-medium tracking-wide text-muted">
      {status}
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
    </span>
  );
}

export function CountPill({ n, kind }: { n: number; kind: "passed" | "failed" | "error" }) {
  const map = {
    passed: { fg: "#22C55E", bg: "#22C55E1A", label: "Passed" },
    failed: { fg: "#EF4444", bg: "#EF44441A", label: "Failed" },
    error: { fg: "#8B8D93", bg: "#8B8D931A", label: "Error" },
  }[kind];
  return (
    <span className="text-xs">
      <span className="font-semibold tabular-nums" style={{ color: map.fg }}>{n}</span>{" "}
      <span className="text-muted">{map.label}</span>
    </span>
  );
}

export function ProbeTag({ probes }: { probes: string[] }) {
  if (probes.length === 0) return <span className="text-xs text-faint">—</span>;
  const first = probes[0];
  const extra = probes.length - 1;
  return (
    <span className="inline-flex items-center gap-1">
      <span className="text-xs px-2 py-[2px] rounded bg-[#1F1F23] text-text">{first}</span>
      {extra > 0 && <span className="text-xs text-muted">+{extra}</span>}
    </span>
  );
}

export function SeverityPill({ severity }: { severity: string }) {
  const color = {
    Critical: "#EF4444", High: "#F59E0B", Medium: "#EAB308", Low: "#A3E635", Info: "#8B8D93",
  }[severity] ?? "#8B8D93";
  return (
    <span
      className="text-[11px] font-semibold px-2 py-[2px] rounded"
      style={{ color, background: `${color}1A` }}
    >
      {severity}
    </span>
  );
}

export function InfoTooltip({ text }: { text: string }) {
  return (
    <span className="ml-1 cursor-help text-faint" title={text}>ⓘ</span>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`bg-card border border-border rounded-card p-5 ${className}`}>
      {children}
    </div>
  );
}

export function CardHeader({ title, tooltip, right }: {
  title: string; tooltip?: string; right?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-4">
      <h3 className="text-base font-semibold text-text">
        {title}
        {tooltip && <InfoTooltip text={tooltip} />}
      </h3>
      {right}
    </div>
  );
}
