"""Domain models shared across engine, judge, and report layers.

These are transport-agnostic pydantic models. SQLAlchemy persistence models
live in store/models.py and map onto these.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class Verdict(enum.StrEnum):
    PASS = "PASS"          # noqa: S105 — enum member, not a credential
                                 # target refused / handled correctly
    PARTIAL = "PARTIAL"    # ambiguous or partial compliance
    FAIL = "FAIL"          # target complied with harmful intent
    ERROR = "ERROR"        # probe could not be evaluated (transport/parse)
    PENDING = "PENDING"    # not yet judged


class Severity(enum.StrEnum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info"


# Ordered worst-first for threshold comparisons.
SEVERITY_ORDER: list[Severity] = [
    Severity.INFO, Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL,
]


class RiskBand(enum.StrEnum):
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"
    CRITICAL = "Critical"


class RunStatus(enum.StrEnum):
    QUEUED = "QUEUED"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    JUDGE = "JUDGE"
    MUTATE = "MUTATE"
    REPORT = "REPORT"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


TERMINAL_STATUSES = {RunStatus.DONE, RunStatus.FAILED, RunStatus.CANCELED}


class ScopeAttestation(BaseModel):
    """Legal gate: a run cannot start without one of these.

    The engine rejects any target not covered by an unexpired attestation.
    """

    target_pattern: str = Field(description="Hostname or pattern the authorizer approved")
    authorized_by: str = Field(description="Name/email of the authorizing party")
    reference: str = Field(description="Ticket, contract, or engagement reference")
    expires: datetime
    created_at: datetime = Field(default_factory=utcnow)

    def is_valid(self, target_host: str, at: datetime | None = None) -> bool:
        at = at or utcnow()
        if at > self.expires:
            return False
        pat = self.target_pattern.lower()
        # normalize URL-shaped patterns to their hostname
        if "://" in pat:
            from urllib.parse import urlparse
            pat = urlparse(pat).hostname or pat
        pat = pat.strip().lstrip("*.")
        host = target_host.lower()
        return host == pat or host.endswith("." + pat)


class Probe(BaseModel):
    """A single curated attack probe."""

    id: str
    name: str
    category: str = Field(description="OWASP LLM Top 10 family, e.g. prompt_injection")
    owasp: str = Field(default="", description="e.g. LLM01")
    description: str = ""
    severity_if_failed: Severity = Severity.HIGH
    payload: str
    system_context: str = Field(
        default="", description="Optional system prompt wrapped around the probe"
    )
    expected_failure_mode: str = Field(default="", description="What a FAIL looks like")
    tags: list[str] = Field(default_factory=list)
    # Multi-turn chain support: follow-up user messages sent in the SAME
    # conversation after the opening payload. Empty = classic single-shot.
    # The engine judges the FINAL response against the full dialogue intent.
    turns: list[str] = Field(default_factory=list)


class Attempt(BaseModel):
    """One probe fired at the target, plus its outcome."""

    id: str
    run_id: str
    probe_id: str
    category: str
    sent_payload: str
    target_response: str = ""
    verdict: Verdict = Verdict.PENDING
    severity: Severity | None = None
    judge_rationale: str = ""
    quoted_span: str = Field(default="", description="Exact response text justifying the verdict")
    judge_engine: str = Field(default="", description="prefilter | llm | dual")
    judge_manipulation: bool = Field(
        default=False, description="Payload tried to influence the judge"
    )
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    error: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class Evidence(BaseModel):
    """Tamper-evident artifact: hash + chained HMAC so reports are auditable."""

    id: str
    run_id: str
    attempt_id: str
    kind: str = "attempt"  # attempt | log | report
    sha256: str
    prev_hmac: str = ""
    hmac: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class CategoryScore(BaseModel):
    category: str
    score: float
    passed: int
    failed: int
    partial: int
    errors: int


class OverallScore(BaseModel):
    score: float
    band: RiskBand
    simulated: int
    successful: int
    categories: list[CategoryScore] = Field(default_factory=list)
    last_run_at: datetime | None = None


class TriageState(enum.StrEnum):
    """Human disposition of a finding — the governance workflow state."""

    OPEN = "open"
    ACCEPTED_RISK = "accepted_risk"
    FALSE_POSITIVE = "false_positive"
    PATCHED = "patched"


class Finding(BaseModel):
    id: str
    run_id: str
    attempt_id: str
    title: str
    category: str
    owasp: str
    severity: Severity
    verdict: Verdict
    quoted_span: str
    judge_rationale: str
    evidence_sha256: str = ""
    needs_human_review: bool = False
    triage_state: str = TriageState.OPEN.value
    triage_note: str = ""


class RunBudget(BaseModel):
    """Hard caps. The engine aborts (never hangs) when any cap is hit."""

    max_probes: int = 100
    max_mutations_per_probe: int = 4
    max_tokens: int = 500_000
    max_cost_usd: float = 10.0
    timeout_seconds: int = 1800
