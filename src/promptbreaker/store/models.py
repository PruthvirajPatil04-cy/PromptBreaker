"""SQLAlchemy persistence models.

Same models run on SQLite (dev) and Postgres (prod) — only DATABASE_URL
changes. Migrations use expand-contract style so a deploy is always
backward-compatible for one release.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class RunRow(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    suite: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str] = mapped_column(Text)
    adapter: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), index=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_band: Mapped[str | None] = mapped_column(String(16), nullable=True)
    simulated: Mapped[int] = mapped_column(Integer, default=0)
    successful: Mapped[int] = mapped_column(Integer, default=0)
    abort_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attested_by: Mapped[str] = mapped_column(Text, default="")
    attestation_ref: Mapped[str] = mapped_column(Text, default="")
    resumed_from: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditRow(Base):
    """Who called what, when — one row per authenticated API request."""

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    role: Mapped[str] = mapped_column(String(16), default="admin")
    method: Mapped[str] = mapped_column(String(8))
    path: Mapped[str] = mapped_column(Text)
    status: Mapped[int] = mapped_column(Integer, default=200)
    detail: Mapped[str] = mapped_column(Text, default="")


class FindingRow(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    attempt_id: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), index=True)
    owasp: Mapped[str] = mapped_column(String(16), default="")
    severity: Mapped[str] = mapped_column(String(16), index=True)
    verdict: Mapped[str] = mapped_column(String(16))
    quoted_span: Mapped[str] = mapped_column(Text, default="")
    judge_rationale: Mapped[str] = mapped_column(Text, default="")
    evidence_sha256: Mapped[str] = mapped_column(String(64), default="")
    needs_human_review: Mapped[int] = mapped_column(Integer, default=0)
    # governance workflow: open | accepted_risk | false_positive | patched
    triage_state: Mapped[str] = mapped_column(String(24), default="open", index=True)
    triage_note: Mapped[str] = mapped_column(Text, default="")
    triaged_by: Mapped[str] = mapped_column(String(64), default="")
    triage_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AttemptRow(Base):
    __tablename__ = "attempts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    probe_id: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    verdict: Mapped[str] = mapped_column(String(16))
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    judge_engine: Mapped[str] = mapped_column(String(16), default="")
    judge_manipulation: Mapped[int] = mapped_column(Integer, default=0)
    judge_rationale: Mapped[str] = mapped_column(Text, default="")
    quoted_span: Mapped[str] = mapped_column(Text, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # payload/response are redacted before persistence (see redact.py)
    sent_payload: Mapped[str] = mapped_column(Text, default="")
    target_response: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EvidenceRow(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    attempt_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16), default="attempt")
    sha256: Mapped[str] = mapped_column(String(64))
    prev_hmac: Mapped[str] = mapped_column(String(64), default="")
    hmac: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TargetRow(Base):
    __tablename__ = "targets"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    adapter: Mapped[str] = mapped_column(String(32), default="openai")
    endpoint: Mapped[str] = mapped_column(Text)
    secret_ref: Mapped[str] = mapped_column(String(256), default="")
    allow_private: Mapped[int] = mapped_column(Integer, default=0)
    max_redirects: Mapped[int] = mapped_column(Integer, default=3)
    sandbox: Mapped[int] = mapped_column(Integer, default=0)
    verified: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EventRow(Base):
    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(32))
    ts: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class ApiKeyRow(Base):
    """RBAC API keys issued from the dashboard. Hash-only (sha256); the
    plaintext is shown exactly once at creation and never stored."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(64))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    prefix: Mapped[str] = mapped_column(String(12), default="")  # display only
    role: Mapped[str] = mapped_column(String(16), default="viewer")
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ScheduleRow(Base):
    """Scheduled scans — recurring runs fired by the in-process scheduler."""

    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(16))
    suite: Mapped[str] = mapped_column(String(64), default="core")
    interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    attested_by: Mapped[str] = mapped_column(Text, default="")
    attestation_ref: Mapped[str] = mapped_column(Text, default="")
    attestation_expires: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_id: Mapped[str] = mapped_column(String(32), default="")
    last_error: Mapped[str] = mapped_column(Text, default="")
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MutationStatRow(Base):
    """Adaptive mutation memory: which mutators defeat which targets."""

    __tablename__ = "mutation_stats"

    target: Mapped[str] = mapped_column(String(128), primary_key=True)
    mutator: Mapped[str] = mapped_column(String(32), primary_key=True)
    tries: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
