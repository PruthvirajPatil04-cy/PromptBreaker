"""Response schemas — camelCase JSON that mirrors dashboard/lib/types.ts.

Every field name here is contract-locked to the TypeScript types the
dashboard renders. If it changes, the contract test in
tests/test_api_contract.py fails — that is the point.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=lambda s: _camel(s))


def _camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(w.capitalize() for w in rest)


# ------------------------------------------------------------------ overview

class CategoryScoreOut(CamelModel):
    category: str
    score: float
    passed: int
    failed: int
    partial: int
    errors: int


class OverallOut(CamelModel):
    score: float
    band: str
    simulated: int
    successful: int
    categories: list[CategoryScoreOut] = Field(default_factory=list)
    last_run_at: datetime | None = None
    trend: list[float] = Field(default_factory=list)


class RecentRunOut(CamelModel):
    run_id: str
    name: str
    target: str = ""
    executed_on: datetime | None = None
    probes: list[str] = Field(default_factory=list)
    passed: int = 0
    failed: int = 0
    errors: int = 0
    progress_pct: int = 0
    status: str
    source: str = "manual"


class SuiteCardOut(CamelModel):
    suite_id: str
    name: str
    category: str
    executed_on: datetime | None = None
    status: str  # FINISHED | PENDING | RUNNING
    passed: int = 0
    failed: int = 0
    errors: int = 0


class CategoryGroupOut(CamelModel):
    category: str
    score: float
    suites: list[SuiteCardOut] = Field(default_factory=list)


class OverviewOut(CamelModel):
    overall: OverallOut
    recent_runs: list[RecentRunOut] = Field(default_factory=list)
    suites_by_category: list[CategoryGroupOut] = Field(default_factory=list)


# ------------------------------------------------------------------ run detail

class BudgetSlotOut(CamelModel):
    used: float
    cap: float


class BudgetOut(CamelModel):
    probes: BudgetSlotOut
    tokens: BudgetSlotOut
    cost_usd: BudgetSlotOut


class FindingOut(CamelModel):
    id: str
    run_id: str
    attempt_id: str
    title: str
    category: str
    owasp: str = ""
    severity: str
    verdict: str
    quoted_span: str = ""
    judge_rationale: str = ""
    judge_engine: str = ""
    judge_manipulation: bool = False
    evidence_sha256: str = ""
    needs_human_review: bool = False
    triage_state: str = "open"      # open | accepted_risk | false_positive | patched
    triage_note: str = ""


class ReviewItemOut(FindingOut):
    """Review-queue row: finding + enough run context to make the call."""
    target: str = ""
    created_at: datetime | None = None


class RunDetailOut(CamelModel):
    run_id: str
    name: str
    status: str
    target: str
    adapter: str
    suite: str
    executed_on: datetime | None = None
    score: float = 0.0
    band: str = "Low"
    simulated: int = 0
    successful: int = 0
    categories: list[CategoryScoreOut] = Field(default_factory=list)
    budget: BudgetOut
    findings: list[FindingOut] = Field(default_factory=list)
    evidence_chain_valid: bool = True
    abort_reason: str = ""  # why a run failed (budget cap, restart, transport…)
    judge_summary: dict[str, int] = Field(default_factory=dict)  # prefilter/llm/…
    attempt_count: int = 0
    resumed_from: str = ""  # set when this run resumed an earlier failed run


# ------------------------------------------------------------------ registries

class ProbeOut(CamelModel):
    id: str
    name: str
    category: str
    owasp: str = ""
    enabled: bool = True
    severity: str
    weight: float = 1.0
    tags: list[str] = Field(default_factory=list)


class ComplianceOut(CamelModel):
    id: str
    framework: str
    title: str
    coverage_pct: int = 0
    status: str  # pass | partial | gap
    linked_finding_ids: list[str] = Field(default_factory=list)


class TargetOut(CamelModel):
    id: str
    name: str
    adapter: str
    endpoint: str
    secret_ref: str = ""
    allow_private: bool = False
    max_redirects: int = 3
    sandbox: bool = False
    verified: bool = False


class TargetIn(CamelModel):
    name: str
    adapter: str = "openai"
    endpoint: str
    secret_ref: str = ""
    allow_private: bool = False
    max_redirects: int = 3
    sandbox: bool = False
    verified: bool = False


class HardeningOut(CamelModel):
    id: str
    finding_id: str
    title: str
    severity: str
    before: str
    after: str
    status: str = "open"


class LogEventOut(CamelModel):
    seq: int
    run_id: str
    type: str
    ts: str
    level: str = "info"
    probe_id: str | None = None
    detail: str | None = None


# ------------------------------------------------------------------ compare

class CompareSideOut(CamelModel):
    run_id: str
    name: str
    target: str = ""
    suite: str = ""
    status: str
    score: float = 0.0
    band: str = ""
    executed_on: datetime | None = None
    simulated: int = 0
    successful: int = 0
    finding_count: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    failing_probes: dict[str, str] = Field(default_factory=dict)  # probe id -> worst severity


class CompareOut(CamelModel):
    a: CompareSideOut
    b: CompareSideOut
    delta_score: float = 0.0
    severity_delta: dict[str, int] = Field(default_factory=dict)  # b minus a
    fixed_in_b: list[str] = Field(default_factory=list)  # failing in A, clean in B
    new_in_b: list[str] = Field(default_factory=list)    # failing in B, clean in A


# ------------------------------------------------------------------ suites + audit

class SuiteOut(CamelModel):
    name: str
    probes: int
    description: str = ""
    builtin: bool = False


class AuditOut(CamelModel):
    id: str
    ts: datetime
    role: str
    method: str
    path: str
    status: int
    detail: str = ""


# ------------------------------------------------------------------ v1.2: keys

class KeyIn(CamelModel):
    name: str
    role: str = "viewer"  # admin | viewer


class KeyOut(CamelModel):
    id: str
    name: str
    prefix: str       # display-only prefix; never the full key
    role: str
    created_at: datetime | None = None
    created_by: str = ""
    revoked: bool = False


class KeyCreatedOut(KeyOut):
    key: str = ""  # plaintext, returned exactly once at creation


# --------------------------------------------------------------- v1.2: triage

class TriageIn(CamelModel):
    triage_state: str  # open | accepted_risk | false_positive | patched
    triage_note: str = ""


# ------------------------------------------------------------- v1.2: schedules

class AttestationIn(CamelModel):
    """Wire form of ScopeAttestation — camelCase (or snake, populate_by_name)."""
    target_pattern: str
    authorized_by: str
    reference: str
    expires: datetime


class ScheduleIn(CamelModel):
    name: str
    target_id: str
    suite: str = "core"
    interval_minutes: int = 60
    enabled: bool = True
    attestation: AttestationIn


class SchedulePatchIn(CamelModel):
    enabled: bool


class ScheduleOut(CamelModel):
    id: str
    name: str
    target_id: str
    suite: str
    interval_minutes: int
    enabled: bool
    attested_by: str = ""
    attestation_ref: str = ""
    attestation_expires: datetime | None = None
    last_run_at: datetime | None = None
    last_run_id: str = ""
    last_error: str = ""
    next_run_at: datetime | None = None


# ---------------------------------------------------------- v1.2: target health

class VerifyTargetOut(CamelModel):
    target_id: str
    verified: bool
    latency_ms: int = 0
    detail: str = ""
