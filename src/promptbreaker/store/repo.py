"""Repository: persist a finished RunResult, load runs/findings back.

Payloads and responses are redacted before they touch the DB (see
security/redact.py) — captured transcripts routinely contain real keys.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from promptbreaker.engine.runner import RunResult
from promptbreaker.models import Attempt, Evidence, Finding, Severity, Verdict
from promptbreaker.security.redact import redact
from promptbreaker.store.models import AttemptRow, EvidenceRow, FindingRow, RunRow


async def save_result(
    session: AsyncSession, result: RunResult, *,
    target: str, adapter: str, attested_by: str = "", attestation_ref: str = "",
) -> str:
    """Persist a completed run. Returns the run id."""
    s = result.score
    run = RunRow(
        id=result.run_id, suite="", target=target, adapter=adapter,
        status=result.status.value,
        score=s.score if s else None,
        risk_band=s.band.value if s else None,
        simulated=s.simulated if s else 0,
        successful=s.successful if s else 0,
        abort_reason=result.abort_reason or None,
        budget=result.budget,
        attested_by=attested_by, attestation_ref=attestation_ref,
        finished_at=datetime.now(timezone.utc),
    )
    session.add(run)

    for a in result.attempts:
        session.add(AttemptRow(
            id=a.id, run_id=a.run_id, probe_id=a.probe_id, category=a.category,
            verdict=a.verdict.value,
            severity=a.severity.value if a.severity else None,
            judge_engine=a.judge_engine,
            judge_manipulation=1 if a.judge_manipulation else 0,
            judge_rationale=redact(a.judge_rationale),
            quoted_span=redact(a.quoted_span),
            latency_ms=a.latency_ms,
            error=redact(a.error) if a.error else None,
            sent_payload=redact(a.sent_payload),
            target_response=redact(a.target_response),
        ))

    for f in result.findings:
        session.add(FindingRow(
            id=f.id, run_id=f.run_id, attempt_id=f.attempt_id,
            title=redact(f.title), category=f.category, owasp=f.owasp,
            severity=f.severity.value, verdict=f.verdict.value,
            quoted_span=redact(f.quoted_span),
            judge_rationale=redact(f.judge_rationale),
            evidence_sha256=f.evidence_sha256,
            needs_human_review=1 if f.needs_human_review else 0,
        ))

    for e in result.evidence:
        session.add(EvidenceRow(
            id=e.id, run_id=e.run_id, attempt_id=e.attempt_id, kind=e.kind,
            sha256=e.sha256, prev_hmac=e.prev_hmac, hmac=e.hmac,
        ))

    await session.commit()
    return result.run_id


async def list_runs(session: AsyncSession, limit: int = 50) -> list[RunRow]:
    rows = await session.execute(
        select(RunRow).order_by(RunRow.created_at.desc()).limit(limit)
    )
    return list(rows.scalars())


async def get_run(session: AsyncSession, run_id: str) -> RunRow | None:
    return await session.get(RunRow, run_id)


async def get_findings(session: AsyncSession, run_id: str) -> list[FindingRow]:
    rows = await session.execute(
        select(FindingRow).where(FindingRow.run_id == run_id)
    )
    return list(rows.scalars())


async def get_attempts(session: AsyncSession, run_id: str) -> list[AttemptRow]:
    rows = await session.execute(
        select(AttemptRow).where(AttemptRow.run_id == run_id)
    )
    return list(rows.scalars())


def attempt_from_row(row: AttemptRow) -> Attempt:
    return Attempt(
        id=row.id, run_id=row.run_id, probe_id=row.probe_id, category=row.category,
        sent_payload=row.sent_payload, target_response=row.target_response,
        verdict=Verdict(row.verdict),
        severity=Severity(row.severity) if row.severity else None,
        judge_rationale=row.judge_rationale, quoted_span=row.quoted_span,
        judge_engine=row.judge_engine,
        judge_manipulation=bool(row.judge_manipulation),
        latency_ms=row.latency_ms, error=row.error or "",
    )


def finding_from_row(row: FindingRow) -> Finding:
    return Finding(
        id=row.id, run_id=row.run_id, attempt_id=row.attempt_id, title=row.title,
        category=row.category, owasp=row.owasp, severity=Severity(row.severity),
        verdict=Verdict(row.verdict), quoted_span=row.quoted_span,
        judge_rationale=row.judge_rationale, evidence_sha256=row.evidence_sha256,
        needs_human_review=bool(row.needs_human_review),
    )


def evidence_from_row(row: EvidenceRow) -> Evidence:
    return Evidence(
        id=row.id, run_id=row.run_id, attempt_id=row.attempt_id, kind=row.kind,
        sha256=row.sha256, prev_hmac=row.prev_hmac, hmac=row.hmac,
    )
