"""SQLAlchemy persistence models.

Same models run on SQLite (dev) and Postgres (prod) — only DATABASE_URL
changes. Migrations use expand-contract style so a deploy is always
backward-compatible for one release.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
