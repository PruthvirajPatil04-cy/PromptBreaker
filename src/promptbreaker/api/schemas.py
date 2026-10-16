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
