// Single data-access boundary. Components call these typed functions; they
// never import mock.ts directly. Live vs mock is decided ONLY by env:
//   NEXT_PUBLIC_PB_USE_MOCK=false  → talk to the FastAPI engine
//   NEXT_PUBLIC_PB_API_KEY=<key>   → sent as x-api-key (build-time value)
//   NEXT_PUBLIC_PB_API_BASE=...    → engine origin (default http://localhost:8000)
// Failures throw — pages render an error state instead of silently showing
// mock numbers next to live ones (fabricated data would be worse than none).
import type {
  OverviewPayload, RunDetail, ProbeRegistryItem, ComplianceControl,
  TargetConfig, HardeningItem, LogEvent,
} from "./types";
import * as mock from "./mock";

export const USE_MOCK = process.env.NEXT_PUBLIC_PB_USE_MOCK !== "false";
const API_BASE = process.env.NEXT_PUBLIC_PB_API_BASE ?? "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_PB_API_KEY ?? "";

/** Start-scan input: target resolved from Targets, attestation is mandatory. */
export interface StartRunInput {
  target: string;
  adapter: string;
  suite: string;
  allowPrivate: boolean;
  apiKey?: string;         // target's stored credential, sent as Bearer
  attestation: {
    targetPattern: string;
    authorizedBy: string;
    reference: string;
    expires: string; // ISO
  };
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function live<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(API_KEY ? { "x-api-key": API_KEY } : {}),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, `${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

export async function getOverview(): Promise<OverviewPayload> {
  return USE_MOCK ? mock.overview : live<OverviewPayload>("/v1/overview");
}

export async function getRunDetail(runId: string): Promise<RunDetail> {
  return USE_MOCK
    ? { ...mock.runDetail, runId }
    : live<RunDetail>(`/v1/runs/${runId}`);
}

export async function getProbeRegistry(): Promise<ProbeRegistryItem[]> {
  return USE_MOCK ? mock.probeRegistry : live<ProbeRegistryItem[]>("/v1/probes");
}

export async function getCompliance(): Promise<ComplianceControl[]> {
  return USE_MOCK ? mock.complianceControls : live<ComplianceControl[]>("/v1/compliance");
}

export async function getTargets(): Promise<TargetConfig[]> {
  return USE_MOCK ? mock.targets : live<TargetConfig[]>("/v1/targets");
}

export async function getHardening(): Promise<HardeningItem[]> {
  return USE_MOCK ? mock.hardening : live<HardeningItem[]>("/v1/hardening");
}

export async function getLogEvents(runId: string): Promise<LogEvent[]> {
  return USE_MOCK
    ? mock.logEvents.filter((e) => e.runId === runId)
    : live<LogEvent[]>(`/v1/runs/${runId}/events`);
}

export function getProjects() {
  return mock.projects;
}

/** Health probe for the topbar badge (no API key required). */
export async function health(): Promise<{ ok: boolean; version: string }> {
  return live("/healthz");
}

export async function startRun(input: StartRunInput): Promise<{ runId: string }> {
  if (USE_MOCK) return { runId: `r-${Date.now()}` };
  return live("/v1/runs", { method: "POST", body: JSON.stringify(input) });
}

/** Fetch a finished run's markdown report and trigger a browser download. */
export async function liveRunReport(runId: string): Promise<void> {
  if (USE_MOCK) return;
  const { report } = await live<{ report: string }>(
    `/v1/runs/${runId}/report`,
    { method: "POST", body: JSON.stringify({ format: "md" }) },
  );
  const blob = new Blob([report], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `promptbreaker-${runId}.md`;
  a.click();
  URL.revokeObjectURL(url);
}
