// Single data-access boundary. Components call these typed functions; they
// never import mock.ts directly. Swapping to the live engine is a change
// ONLY in this file (flip USE_MOCK and point at the FastAPI base URL).
import type {
  OverviewPayload, RunDetail, ProbeRegistryItem, ComplianceControl,
  TargetConfig, HardeningItem, LogEvent,
} from "./types";
import * as mock from "./mock";

const USE_MOCK = true;
const API_BASE = process.env.NEXT_PUBLIC_PB_API_BASE ?? "http://localhost:8000";

async function live<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
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

export async function startRun(targetId: string, suite: string): Promise<{ runId: string }> {
  return USE_MOCK
    ? { runId: `r-${Date.now()}` }
    : live("/v1/runs", { method: "POST", body: JSON.stringify({ targetId, suite }) });
}
