// API + domain types — these mirror the engine's OpenAPI contract exactly.
// The mock fixtures and the live client both produce these shapes, so
// swapping mock -> live is a single-file change in lib/api.ts.

export type Verdict = "PASS" | "PARTIAL" | "FAIL" | "ERROR" | "PENDING";
export type Severity = "Critical" | "High" | "Medium" | "Low" | "Info";
export type RiskBand = "Low" | "Moderate" | "High" | "Critical";
export type RunStatus =
  | "QUEUED" | "PLAN" | "EXECUTE" | "JUDGE" | "MUTATE" | "REPORT"
  | "DONE" | "FAILED" | "CANCELED";

export interface CategoryScore {
  category: string;
  score: number;
  passed: number;
  failed: number;
  partial: number;
  errors: number;
}

export interface OverallScore {
  score: number;
  band: RiskBand;
  simulated: number;
  successful: number;
  categories: CategoryScore[];
  lastRunAt: string | null;
  trend: number[]; // per-run scores, oldest → newest (last 7 finished runs)
}

export interface RecentRun {
  runId: string;
  name: string;
  target: string;          // endpoint the run hit — lets the list scope per bot
  executedOn: string;
  probes: string[];        // first probe/category shown; extras become "+N"
  passed: number;
  failed: number;
  errors: number;
  progressPct: number;
  status: RunStatus;
  source: "manual" | "ci-github" | "ci-bitbucket";
}

export interface SuiteCard {
  suiteId: string;
  name: string;
  category: string;
  executedOn: string;
  status: "FINISHED" | "PENDING" | "RUNNING";
  passed: number;
  failed: number;
  errors: number;
}

export interface OverviewPayload {
  overall: OverallScore;
  recentRuns: RecentRun[];
  suitesByCategory: { category: string; score: number; suites: SuiteCard[] }[];
}

export interface Finding {
  id: string;
  runId: string;
  attemptId: string;
  title: string;
  category: string;
  owasp: string;
  severity: Severity;
  verdict: Verdict;
  quotedSpan: string;
  judgeRationale: string;
  judgeEngine: string;
  judgeManipulation: boolean;
  evidenceSha256: string;
  needsHumanReview: boolean;
  /** governance workflow: open | accepted_risk | false_positive | patched */
  triageState: TriageState;
  triageNote: string;
}

export type TriageState = "open" | "accepted_risk" | "false_positive" | "patched";

/** Review queue row — finding + run context (GET /v1/review). */
export interface ReviewItem extends Finding {
  target: string;
  createdAt: string | null;
}

/** Which engine decided each verdict in a run (GET /v1/runs/{id}). */
export interface JudgeSummary {
  prefilter: number;
  llm: number;
  none: number;
  dual: number;
  manipulation: number;
  humanReview: number;
}

export interface RunDetail {
  runId: string;
  name: string;
  status: RunStatus;
  abortReason: string; // why it failed: budget cap, restart, transport…
  target: string;
  adapter: string;
  suite: string;
  executedOn: string;
  score: number;
  band: RiskBand;
  simulated: number;
  successful: number;
  categories: CategoryScore[];
  budget: { probes: { used: number; cap: number }; tokens: { used: number; cap: number }; costUsd: { used: number; cap: number } };
  findings: Finding[];
  evidenceChainValid: boolean;
  judgeSummary: JudgeSummary;   // per-run judge breakdown panel
  attemptCount: number;
  resumedFrom: string;          // set when this run resumed an earlier failed run
}

export interface ProbeRegistryItem {
  id: string;
  name: string;
  category: string;
  owasp: string;
  enabled: boolean;
  severity: Severity;
  weight: number;
  tags: string[];
}

export interface ComplianceControl {
  id: string;
  framework: "OWASP-LLM" | "NIST-AI-RMF";
  title: string;
  coveragePct: number;
  status: "pass" | "partial" | "gap";
  linkedFindingIds: string[];
}

export interface SuiteInfo {
  name: string;
  probes: number;
  description: string;
  builtin: boolean; // shipped suite — protected from overwrite/delete
}

/** Run-vs-run comparison (GET /v1/compare?a=&b=) — delta view for the Compare page. */
export interface CompareSide {
  runId: string;
  name: string;
  target: string;
  suite: string;
  status: RunStatus;
  score: number;
  band: string;
  executedOn: string | null;
  simulated: number;
  successful: number;
  findingCount: number;
  bySeverity: Record<string, number>;
  byCategory: Record<string, number>;
  failingProbes: Record<string, string>; // probe id → worst severity
}

export interface CompareResult {
  a: CompareSide;
  b: CompareSide;
  deltaScore: number;
  severityDelta: Record<string, number>; // b minus a, per severity
  fixedInB: string[]; // failing in A, clean in B
  newInB: string[];   // failing in B, clean in A
}

/** Audit log entry (GET /v1/audit) — one row per authenticated API request. */
export interface AuditEvent {
  id: string;
  ts: string;
  role: string;
  method: string;
  path: string;
  status: number;
  detail: string;
}

export interface TargetConfig {
  id: string;
  name: string;
  adapter: "openai" | "ollama" | "http" | "anthropic" | "mcp";
  endpoint: string;
  secretRef: string;        // never plaintext — reference only
  allowPrivate: boolean;
  maxRedirects: number;
  sandbox: boolean;
  verified: boolean;
}

export interface HardeningItem {
  id: string;
  findingId: string;
  title: string;
  severity: Severity;
  before: string;
  after: string;
  status: "open" | "accepted" | "dismissed";
}

export interface LogEvent {
  seq: number;
  runId: string;
  type: string;
  ts: string;
  level: "info" | "warn" | "error";
  probeId?: string;
  detail?: string;
}

/** Dashboard-issued API key (GET /v1/keys). Plaintext only ever returned once. */
export interface ApiKey {
  id: string;
  name: string;
  prefix: string;      // display prefix — never the full key
  role: "admin" | "viewer";
  createdAt: string | null;
  createdBy: string;
  revoked: boolean;
}

export interface CreatedApiKey extends ApiKey {
  key: string; // plaintext, shown exactly once at creation
}

/** Scheduled scan (GET /v1/schedules). */
export interface Schedule {
  id: string;
  name: string;
  targetId: string;
  suite: string;
  intervalMinutes: number;
  enabled: boolean;
  attestedBy: string;
  attestationRef: string;
  attestationExpires: string | null;
  lastRunAt: string | null;
  lastRunId: string;
  lastError: string;
  nextRunAt: string | null;
}

/** Pre-stage health check result (POST /v1/targets/{id}/verify). */
export interface VerifyTargetResult {
  targetId: string;
  verified: boolean;
  latencyMs: number;
  detail: string;
}
