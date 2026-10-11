"use client";
// Pure-SVG semicircular gauge. value 0-100, band color from scoring.
import { bandColor, riskBand } from "@/lib/scoring";

export function GaugeChart({ value, size = 220 }: { value: number; size?: number }) {
  const band = riskBand(value);
  const stroke = bandColor(band);
  const r = size / 2 - 18;
  const cx = size / 2;
  const cy = size / 2 + 10;
  // semicircle arc from 180deg to 0deg (top half)
  const circumference = Math.PI * r;
  const pct = Math.min(100, Math.max(0, value)) / 100;
  const dash = circumference * pct;

  return (
    <svg width={size} height={size / 2 + 24} viewBox={`0 0 ${size} ${size / 2 + 24}`}>
      {/* track */}
      <path
        d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
        fill="none"
        stroke="#1F1F23"
        strokeWidth={16}
        strokeLinecap="round"
      />
      {/* value arc */}
      <path
        d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
        fill="none"
        stroke={stroke}
        strokeWidth={16}
        strokeLinecap="round"
        strokeDasharray={`${dash} ${circumference}`}
      />
    </svg>
  );
}
