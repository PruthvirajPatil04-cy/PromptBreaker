"use client";
// Donut ring for suite cards: passed (green) vs failed (red), remainder track.
export function DonutRing({
  passed, failed, size = 64, strokeWidth = 8, dim = false,
}: { passed: number; failed: number; size?: number; strokeWidth?: number; dim?: boolean }) {
  const total = passed + failed;
  const r = size / 2 - strokeWidth / 2 - 1;
  const c = 2 * Math.PI * r;
  const failFrac = total === 0 ? 0 : failed / total;
  const passFrac = total === 0 ? 0 : passed / total;

  if (total === 0) {
    return (
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#2A2A30" strokeWidth={strokeWidth} />
      </svg>
    );
  }

  return (
    <svg width={size} height={size} style={{ opacity: dim ? 0.4 : 1 }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#1F1F23" strokeWidth={strokeWidth} />
      {/* failed arc (starts at top) */}
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke="#EF4444" strokeWidth={strokeWidth}
        strokeDasharray={`${c * failFrac} ${c}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      {/* passed arc (after failed) */}
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke="#22C55E" strokeWidth={strokeWidth}
        strokeDasharray={`${c * passFrac} ${c}`}
        strokeDashoffset={-c * failFrac}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
    </svg>
  );
}
