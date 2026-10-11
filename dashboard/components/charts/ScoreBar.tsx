"use client";
// Horizontal score bar for Category Scores.
import { scoreColor } from "@/lib/scoring";

export function ScoreBar({ label, score }: { label: string; score: number }) {
  const color = scoreColor(score);
  const pct = Math.min(100, Math.max(0, score));
  return (
    <div className="mb-3 last:mb-0">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-text">{label}</span>
        <span
          className="text-xs font-medium tabular-nums px-2 py-[2px] rounded"
          style={{ color, background: `${color}1A` }}
        >
          {score.toFixed(2)}
        </span>
      </div>
      <div className="h-2 rounded-full bg-[#1F1F23] overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}
