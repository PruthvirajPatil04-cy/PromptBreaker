"""Repository: persist a finished RunResult, load runs/findings back.

Payloads and responses are redacted before they touch the DB (see
security/redact.py) — captured transcripts routinely contain real keys.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from promptbreaker.engine.runner import RunResult
from promptbreaker.models import (
    TERMINAL_STATUSES,
    Attempt,
    Evidence,
    Finding,
    RunStatus,
    Severity,
    Verdict,
)
from promptbreaker.security.redact import redact
from promptbreaker.store.models import (
    ApiKeyRow,
    AttemptRow,
    EvidenceRow,
    FindingRow,
    MutationStatRow,
    RunRow,
    ScheduleRow,
)

if TYPE_CHECKING:
    from promptbreaker.store.models import AuditRow, EventRow


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
    run.finished_at = datetime.now(UTC)

    # attempts may already exist from incremental persistence (save_attempt)
    from sqlalchemy import select as _select
    already = {
        r for (r,) in await session.execute(
            _select(AttemptRow.id).where(AttemptRow.run_id == result.run_id)
        )
    }
    for a in result.attempts:
        if a.id in already:
            continue
        session.add(AttemptRow(
            id=a.id, run_id=a.run_id, probe_id=a.probe_id, category=a.category,
            verdict=a.verdict.value,
            severity=a.severity.value if a.severity else None,
            judge_engine=a.judge_engine,
            judge_manipulation=1 if a.judge_manipulation else 0,
            judge_rationale=redact(a.judge_rationale),
            quoted_span=redact(a.quoted_span),
            latency_ms=a.latency_ms,
            tokens_in=a.tokens_in,
            tokens_out=a.tokens_out,
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
    resumed_from: str | None = None,
) -> None:
    """Insert a QUEUED run row at creation time so the dashboard can show it
    immediately — not only after completion."""
    session.add(RunRow(
        id=run_id, suite=suite, target=target, adapter=adapter,
        status="QUEUED", attested_by=attested_by, attestation_ref=attestation_ref,
        resumed_from=resumed_from,
    ))
    await session.commit()


async def save_attempt(session: AsyncSession, attempt: Attempt) -> None:
    """Incremental persistence: one row per attempt as it completes.

    A crash mid-run keeps everything already judged instead of losing the
    whole run, and the resume flow can see exactly which probes executed.
    """
    from sqlalchemy import select as _select

    exists = (await session.execute(
        _select(AttemptRow.id).where(AttemptRow.id == attempt.id)
    )).first()
    if exists:
        return
    session.add(AttemptRow(
        id=attempt.id, run_id=attempt.run_id, probe_id=attempt.probe_id,
        category=attempt.category, verdict=attempt.verdict.value,
        severity=attempt.severity.value if attempt.severity else None,
        judge_engine=attempt.judge_engine,
        judge_manipulation=1 if attempt.judge_manipulation else 0,
        judge_rationale=redact(attempt.judge_rationale),
        quoted_span=redact(attempt.quoted_span),
        latency_ms=attempt.latency_ms,
        tokens_in=attempt.tokens_in,
        tokens_out=attempt.tokens_out,
        error=redact(attempt.error) if attempt.error else None,
        sent_payload=redact(attempt.sent_payload),
        target_response=redact(attempt.target_response),
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


async def fail_interrupted_runs(
    session: AsyncSession, reason: str = "interrupted by API restart",
) -> int:
    """Startup recovery: runs left non-terminal are marked FAILED.

    The engine holds tasks in memory only, so a restart orphans anything
    mid-flight — without this those rows report as running forever.
    """
    rows = (
        (await session.execute(
            select(RunRow).where(RunRow.status.notin_([s.value for s in TERMINAL_STATUSES]))
        )).scalars().all()
    )
    now = datetime.now(UTC)
    for run in rows:
        run.status = RunStatus.FAILED.value
        run.abort_reason = reason
        run.finished_at = run.finished_at or now
    await session.commit()
    return len(rows)


async def list_runs(session: AsyncSession, limit: int = 50) -> list[RunRow]:
    rows = await session.execute(
        select(RunRow).order_by(RunRow.created_at.desc()).limit(limit)
    )
    return list(rows.scalars())


async def run_verdict_counts(
    session: AsyncSession, run_ids: list[str],
) -> dict[str, dict[str, int]]:
    """Per-run PASS/FAIL/PARTIAL/ERROR counts + distinct probe ids, one query."""
    from sqlalchemy import func

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


async def get_events(session: AsyncSession, run_id: str) -> list[EventRow]:
    from promptbreaker.store.models import EventRow
    rows = await session.execute(
        select(EventRow).where(EventRow.run_id == run_id).order_by(EventRow.seq)
    )
    return list(rows.scalars())


# ---------------------------------------------------------------- targets

async def list_targets(session: AsyncSession) -> list[TargetRow]:
    from sqlalchemy import select as _select
    rows = await session.execute(_select(TargetRow).order_by(TargetRow.created_at))
    return list(rows.scalars())


async def add_target(session: AsyncSession, *, name: str, adapter: str, endpoint: str,
                     secret_ref: str = "", allow_private: bool = False,
                     max_redirects: int = 3, sandbox: bool = False,
                     verified: bool = False) -> TargetRow:
    import uuid as _uuid

    from promptbreaker.store.models import TargetRow
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
        tokens_in=row.tokens_in, tokens_out=row.tokens_out,
        latency_ms=row.latency_ms, error=row.error or "",
    )


def finding_from_row(row: FindingRow) -> Finding:
    return Finding(
        id=row.id, run_id=row.run_id, attempt_id=row.attempt_id, title=row.title,
        category=row.category, owasp=row.owasp, severity=Severity(row.severity),
        verdict=Verdict(row.verdict), quoted_span=row.quoted_span,
        judge_rationale=row.judge_rationale, evidence_sha256=row.evidence_sha256,
        needs_human_review=bool(row.needs_human_review),
        triage_state=row.triage_state or "open",
        triage_note=row.triage_note or "",
    )


def evidence_from_row(row: EvidenceRow) -> Evidence:
    return Evidence(
        id=row.id, run_id=row.run_id, attempt_id=row.attempt_id, kind=row.kind,
        sha256=row.sha256, prev_hmac=row.prev_hmac, hmac=row.hmac,
    )


# ---------------------------------------------------------------- audit + metrics

async def add_audit(session: AsyncSession, *, role: str, method: str, path: str,
                    status: int, detail: str = "") -> None:
    from promptbreaker.store.models import AuditRow
    session.add(AuditRow(
        role=role[:16], method=method[:8], path=path[:500],
        status=status, detail=detail[:500],
    ))
    await session.commit()


async def list_audit(session: AsyncSession, limit: int = 200) -> list[AuditRow]:
    from sqlalchemy import select as _select

    from promptbreaker.store.models import AuditRow
    rows = await session.execute(
        _select(AuditRow).order_by(AuditRow.ts.desc()).limit(limit)
    )
    return list(rows.scalars())


async def metrics_counts(session: AsyncSession) -> dict[str, dict[str, int]]:
    """Aggregate counters for /metrics: runs by status, findings by severity,
    attempts by verdict. Single GROUP BY each — cheap at any row count."""
    from sqlalchemy import func

    out: dict[str, dict[str, int]] = {"runs": {}, "findings": {}, "attempts": {}}

    async def group(col, key_out: dict) -> None:
        rows = await session.execute(
            select(col, func.count()).group_by(col)
        )
        for value, count in rows:
            key_out[str(value)] = int(count)

    await group(RunRow.status, out["runs"])
    await group(FindingRow.severity, out["findings"])
    await group(AttemptRow.verdict, out["attempts"])
    return out


# ---------------------------------------------------------------- triage

async def get_finding(session: AsyncSession, finding_id: str) -> FindingRow | None:
    return await session.get(FindingRow, finding_id)


async def set_finding_triage(
    session: AsyncSession, finding_id: str, *, state: str, note: str = "",
    triaged_by: str = "",
) -> FindingRow | None:
    """Human disposition of a finding — the governance state machine."""
    from promptbreaker.models import TriageState

    row = await session.get(FindingRow, finding_id)
    if row is None:
        return None
    if state not in {s.value for s in TriageState}:
        raise ValueError(f"invalid triage state {state!r}")
    row.triage_state = state
    row.triage_note = note[:1000]
    row.triaged_by = triaged_by[:64]
    row.triage_at = datetime.now(UTC)
    await session.commit()
    return row


async def list_review_findings(session: AsyncSession, limit: int = 200) -> list[FindingRow]:
    """Review queue: untriaged findings that carry weight — every Critical
    (human review required by policy) plus any High still open."""
    rows = await session.execute(
        select(FindingRow)
        .where(
            FindingRow.triage_state == "open",
            FindingRow.severity.in_(["Critical", "High"]),
        )
        .order_by(FindingRow.created_at.desc())
        .limit(limit)
    )
    return list(rows.scalars())


async def review_queue_depth(session: AsyncSession) -> int:
    from sqlalchemy import func

    return int((await session.execute(
        select(func.count()).select_from(FindingRow).where(
            FindingRow.triage_state == "open",
            FindingRow.severity.in_(["Critical", "High"]),
        )
    )).scalar() or 0)


# ---------------------------------------------------------------- API keys

async def list_api_keys(session: AsyncSession) -> list[ApiKeyRow]:
    rows = await session.execute(select(ApiKeyRow).order_by(ApiKeyRow.created_at.desc()))
    return list(rows.scalars())


async def add_api_key(
    session: AsyncSession, *, name: str, key_hash: str, prefix: str,
    role: str, created_by: str = "",
) -> ApiKeyRow:
    row = ApiKeyRow(
        name=name[:64], key_hash=key_hash, prefix=prefix[:12],
        role=role, created_by=created_by[:64],
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def revoke_api_key(session: AsyncSession, key_id: str) -> bool:
    row = await session.get(ApiKeyRow, key_id)
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = datetime.now(UTC)
    await session.commit()
    return True


async def find_api_key(session: AsyncSession, key_hash: str) -> ApiKeyRow | None:
    """Active (non-revoked) key row for a sha256 digest, or None."""
    rows = await session.execute(
        select(ApiKeyRow).where(ApiKeyRow.key_hash == key_hash)
    )
    for row in rows.scalars():
        if row.revoked_at is None:
            return row
    return None


# ---------------------------------------------------------------- schedules

async def list_schedules(session: AsyncSession) -> list[ScheduleRow]:
    rows = await session.execute(select(ScheduleRow).order_by(ScheduleRow.created_at))
    return list(rows.scalars())


async def get_schedule(session: AsyncSession, schedule_id: str) -> ScheduleRow | None:
    return await session.get(ScheduleRow, schedule_id)


async def add_schedule(
    session: AsyncSession, *, name: str, target_id: str, suite: str,
    interval_minutes: int, attested_by: str, attestation_ref: str,
    attestation_expires: datetime | None,
) -> ScheduleRow:
    row = ScheduleRow(
        name=name[:64], target_id=target_id, suite=suite,
        interval_minutes=max(1, interval_minutes), enabled=1,
        attested_by=attested_by[:200], attestation_ref=attestation_ref[:200],
        attestation_expires=attestation_expires,
        next_run_at=datetime.now(UTC),  # due immediately on first tick
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def delete_schedule(session: AsyncSession, schedule_id: str) -> bool:
    row = await session.get(ScheduleRow, schedule_id)
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


async def set_schedule_enabled(session: AsyncSession, schedule_id: str, enabled: bool) -> bool:
    row = await session.get(ScheduleRow, schedule_id)
    if row is None:
        return False
    row.enabled = 1 if enabled else 0
    await session.commit()
    return True


async def due_schedules(session: AsyncSession, now: datetime | None = None) -> list[ScheduleRow]:
    now = now or datetime.now(UTC)
    rows = await session.execute(
        select(ScheduleRow).where(ScheduleRow.enabled == 1)
    )
    out = []
    for row in rows.scalars():
        next_at = _naive_to_utc(row.next_run_at or row.created_at)
        if next_at is not None and next_at <= now:
            out.append(row)
    return out


def _naive_to_utc(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; comparisons need tz-aware UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


async def mark_schedule_fired(
    session: AsyncSession, schedule_id: str, *, run_id: str, error: str = "",
) -> None:
    row = await session.get(ScheduleRow, schedule_id)
    if row is None:
        return
    now = datetime.now(UTC)
    row.last_run_at = now
    row.last_run_id = run_id
    row.last_error = error[:500]
    row.next_run_at = now + timedelta(minutes=row.interval_minutes)
    await session.commit()


# ---------------------------------------------------------- mutation stats

async def load_mutation_stats(session: AsyncSession, target: str) -> list[tuple[str, int, int]]:
    rows = await session.execute(
        select(MutationStatRow).where(MutationStatRow.target == target)
    )
    return [(r.mutator, r.tries, r.wins) for r in rows.scalars()]


async def save_mutation_stats(
    session: AsyncSession, target: str, rows: list[tuple[str, int, int]],
) -> None:
    """Upsert adaptive policy stats for a target (called after each run)."""
    for mutator, tries, wins in rows:
        row = await session.get(MutationStatRow, (target, mutator))
        if row is None:
            session.add(MutationStatRow(
                target=target[:128], mutator=mutator, tries=tries, wins=wins,
            ))
        else:
            row.tries, row.wins = tries, wins
            row.updated_at = datetime.now(UTC)
    await session.commit()


# ---------------------------------------------------------------- targets

async def set_target_verified(
    session: AsyncSession, target_id: str, verified: bool,
) -> TargetRow | None:
    row = await session.get(TargetRow, target_id)
    if row is None:
        return None
    row.verified = 1 if verified else 0
    await session.commit()
    return row


async def get_target(session: AsyncSession, target_id: str) -> TargetRow | None:
    return await session.get(TargetRow, target_id)
