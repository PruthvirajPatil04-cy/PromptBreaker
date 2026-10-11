"use client";
// Segmented progress bar (the tick-style bar in Recent Test Runs).
export function SegmentsProgress({
  pct, segments = 12, done, status = "DONE",
}: { pct: number; segments?: number; done?: boolean; status?: string }) {
  const filled = Math.round((Math.min(100, Math.max(0, pct)) / 100) * segments);
  const pending = status === "QUEUED" || status === "PENDING";
  return (
    <div className="flex items-center gap-[3px]">
      {Array.from({ length: segments }).map((_, i) => (
        <span
          key={i}
          className="h-4 w-[5px] rounded-sm"
          style={{ background: i < filled ? "#14B8A6" : "#2A2A30" }}
        />
      ))}
      <span className="ml-2 text-xs text-muted tabular-nums">{pct}%</span>
      {pending ? (
        <span className="ml-1 text-xs text-faint">⏱</span>
      ) : done !== false ? (
        <span className="ml-1 text-xs" style={{ color: "#22C55E" }}>✓</span>
      ) : null}
    </div>
  );
}
