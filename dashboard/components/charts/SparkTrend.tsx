"use client";
// Sparkline trend for the score/trend toggle on Overall Score card.
export function SparkTrend({ points, width = 200, height = 80 }: {
  points: number[]; width?: number; height?: number;
}) {
  if (points.length < 2) return <div className="text-xs text-faint">No trend data</div>;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const step = width / (points.length - 1);
  const coords = points.map((p, i) => [i * step, height - ((p - min) / range) * (height - 8) - 4] as const);
  const path = coords.map(([x, y], i) => (i === 0 ? `M ${x} ${y}` : `L ${x} ${y}`)).join(" ");
  return (
    <svg width={width} height={height}>
      <path d={path} fill="none" stroke="#14B8A6" strokeWidth={2} />
      {coords.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={2.5} fill="#14B8A6" />
      ))}
    </svg>
  );
}
