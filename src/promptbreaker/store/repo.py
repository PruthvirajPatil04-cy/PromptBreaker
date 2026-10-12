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
    target: str, adapter: str, suite: str = "",
    attested_by: str = "", attestation_ref: str = "",
) -> str:
    """Persist a completed run (upsert: a QUEUED row may already exist).

    Returns the run id.
    """
    s = result.score
    run = await session.get(RunRow, result.run_id)
    if run is None:
        run = RunRow(
            id=result.run_id, suite=suite, target=target, adapter=adapter,
            attested_by=attested_by, attestation_ref=attestation_ref,
        )
        session.add(run)
    run.suite = suite or run.suite
    run.status = result.status.value
    run.score = s.score if s else None
    run.risk_band = s.band.value if s else None
    run.simulated = s.simulated if s else 0
    run.successful = s.successful if s else 0
    run.abort_reason = result.abort_reason or None
    run.budget = result.budget
    run.finished_at = datetime.now(timezone.utc)

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


async def create_run(
    session: AsyncSession, *, run_id: str, suite: str, target: str,
    adapter: str, attested_by: str = "", attestation_ref: str = "",
) -> None:
    """Insert a QUEUED run row at creation time so the dashboard can show it
    immediately — not only after completion."""
    session.add(RunRow(
        id=run_id, suite=suite, target=target, adapter=adapter,
        status="QUEUED", attested_by=attested_by, attestation_ref=attestation_ref,
    ))
    await session.commit()


async def set_run_status(
    session: AsyncSession, run_id: str, status: str, *, error: str | None = None,
) -> None:
    run = await session.get(RunRow, run_id)
    if run is None:
        return
    run.status = status
    if error:
        run.abort_reason = error[:500]
    await session.commit()


async def list_runs(session: AsyncSession, limit: int = 50) -> list[RunRow]:
    rows = await session.execute(
        select(RunRow).order_by(RunRow.created_at.desc()).limit(limit)
    )
    return list(rows.scalars())


async def run_verdict_counts(
    session: AsyncSession, run_ids: list[str],
) -> dict[str, dict[str, int]]:
    """Per-run PASS/FAIL/PARTIAL/ERROR counts + distinct probe ids, one query."""
    from sqlalchemy import distinct, func

    out: dict[str, dict[str, int]] = {
        rid: {"passed": 0, "failed": 0, "partial": 0, "errors": 0, "attempts": 0}
        for rid in run_ids
    }
    if not run_ids:
        return out
    rows = await session.execute(
        select(AttemptRow.run_id, AttemptRow.verdict, func.count())
        .where(AttemptRow.run_id.in_(run_ids))
        .group_by(AttemptRow.run_id, AttemptRow.verdict)
    )
    key = {"PASS": "passed", "FAIL": "failed", "PARTIAL": "partial", "ERROR": "errors"}
    for run_id, verdict, n in rows:
        if run_id in out:
            out[run_id][key.get(verdict, "attempts")] += n
            out[run_id]["attempts"] += n
    return out


async def run_probe_ids(
    session: AsyncSession, run_ids: list[str],
) -> dict[str, list[str]]:
    """Distinct probe ids per run, in first-seen order (mutations stripped)."""
    from sqlalchemy import distinct, func

    out: dict[str, list[str]] = {rid: [] for rid in run_ids}
    if not run_ids:
        return out
    rows = await session.execute(
        select(AttemptRow.run_id, AttemptRow.probe_id)
        .where(AttemptRow.run_id.in_(run_ids))
        .order_by(AttemptRow.created_at)
    )
    for run_id, probe_id in rows:
        base = probe_id.split("#")[0]  # PI-001#m-zw -> PI-001
        if run_id in out and base not in out[run_id]:
            out[run_id].append(base)
    return out


async def get_evidence(session: AsyncSession, run_id: str) -> list[EvidenceRow]:
    rows = await session.execute(
        select(EvidenceRow).where(EvidenceRow.run_id == run_id)
        .order_by(EvidenceRow.created_at)
    )
    return list(rows.scalars())


# ---------------------------------------------------------------- events

async def save_events(session: AsyncSession, run_id: str, events: list) -> None:
    """Persist the in-memory event log for a run (survives restarts)."""
    from promptbreaker.store.models import EventRow
    for ev in events:
        session.add(EventRow(
            run_id=run_id, seq=ev.seq, type=ev.type, ts=ev.ts,
            payload=ev.payload or {},
        ))
    await session.commit()


async def get_events(session: AsyncSession, run_id: str) -> list["EventRow"]:
    from promptbreaker.store.models import EventRow
    rows = await session.execute(
        select(EventRow).where(EventRow.run_id == run_id).order_by(EventRow.seq)
    )
    return list(rows.scalars())


# ---------------------------------------------------------------- targets

async def list_targets(session: AsyncSession) -> list["TargetRow"]:
    from sqlalchemy import select as _select
    rows = await session.execute(_select(TargetRow).order_by(TargetRow.created_at))
    return list(rows.scalars())


async def add_target(session: AsyncSession, *, name: str, adapter: str, endpoint: str,
                     secret_ref: str = "", allow_private: bool = False,
                     max_redirects: int = 3, sandbox: bool = False,
                     verified: bool = False) -> "TargetRow":
    from promptbreaker.store.models import TargetRow
    import uuid as _uuid
    row = TargetRow(
        id=f"t-{_uuid.uuid4().hex[:8]}", name=name, adapter=adapter,
        endpoint=endpoint, secret_ref=secret_ref, allow_private=allow_private,
        max_redirects=max_redirects, sandbox=sandbox, verified=verified,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


from promptbreaker.store.models import TargetRow  # noqa: E402  (re-export for callers)


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
