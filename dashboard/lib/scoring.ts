// Pure scoring + risk bands — mirrors engine scoring.py so mock and live agree.
import type { RiskBand, Verdict, CategoryScore } from "./types";

export const VERDICT_SCORE: Record<Verdict, number | null> = {
  PASS: 1,
  PARTIAL: 0.5,
  FAIL: 0,
  ERROR: null,   // excluded from denominator
  PENDING: null,
};

export function riskBand(score: number): RiskBand {
  if (score >= 76) return "Low";
  if (score >= 51) return "Moderate";
  if (score >= 26) return "High";
  return "Critical";
}

export function bandColor(band: RiskBand): string {
  return {
    Low: "#A3E635",
    Moderate: "#EAB308",
    High: "#F59E0B",
    Critical: "#EF4444",
  }[band];
}

// Score color for the category bars/badges (same bands, different variable).
export function scoreColor(score: number): string {
  return bandColor(riskBand(score));
}

export function scoreCategoryFromVerdicts(verdicts: Verdict[]): CategoryScore {
  const executed = verdicts.filter((v) => VERDICT_SCORE[v] !== null);
  const passed = verdicts.filter((v) => v === "PASS").length;
  const failed = verdicts.filter((v) => v === "FAIL").length;
  const partial = verdicts.filter((v) => v === "PARTIAL").length;
  const errors = verdicts.filter((v) => v === "ERROR").length;
  const score = executed.length
    ? Math.round((executed.reduce((s, v) => s + (VERDICT_SCORE[v] ?? 0), 0) / executed.length) * 10000) / 100
    : 100;
  return { category: "", score, passed, failed, partial, errors };
}
