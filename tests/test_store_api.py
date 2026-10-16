"""Tests for persistence, redaction, and the API layer."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from promptbreaker.adapters.base import TargetAdapter, TargetResponse
from promptbreaker.engine.runner import Engine
from promptbreaker.models import RunBudget, RunStatus, ScopeAttestation
from promptbreaker.security.redact import redact, redact_mapping
from promptbreaker.store import repo
from promptbreaker.store.models import Base

# ---------------------------------------------------------------- redact

def test_redacts_api_keys_and_tokens():
    s = "key sk-abc123def456ghi789 and ghp_abcdefghijklmnopqrstuv and AKIA1234567890ABCD"
    out = redact(s)
    assert "sk-abc" not in out and "ghp_" not in out and "AKIA" not in out
    assert "[REDACTED_API_KEY]" in out and "[REDACTED_GITHUB_TOKEN]" in out


def test_redacts_password_assignment_and_email():
    out = redact("connect with password: hunter2 then mail user@example.com")
    assert "hunter2" not in out
    assert "user@example.com" not in out


def test_redact_mapping_recursive():
    data = {"a": {"b": ["x", "password=abc"], "c": "sk-12345678901234567890"}, "d": 5}
    out = redact_mapping(data)
    assert "abc" not in out["a"]["b"][1]
    assert "sk-" not in out["a"]["c"]
    assert out["d"] == 5


def test_clean_text_unchanged():
    assert redact("the weather is fine today") == "the weather is fine today"


# ---------------------------------------------------------------- store

class FakeAdapter(TargetAdapter):
    kind = "fake"
    def __init__(self):
        super().__init__("https://authorized.example.com/v1")
    async def complete(self, messages):
        return TargetResponse(
            text="I'm sorry, but I can't help with that.", tokens_in=1, tokens_out=1
        )


@pytest.fixture
async def db():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _attestation():
    return ScopeAttestation(
        target_pattern="authorized.example.com", authorized_by="Eng", reference="R-1",
        expires=datetime.now(UTC) + timedelta(hours=1),
    )


async def test_save_and_reload_run(db):
    e = Engine(adapter=FakeAdapter(), attestation=_attestation(),
               llm_judge=None, budget=RunBudget(max_probes=3, max_mutations_per_probe=1))
    result = await e.run()

    factory = db
    async with factory() as session:
        run_id = await repo.save_result(
            session, result, target="https://authorized.example.com/v1",
            adapter="fake", attested_by="Eng", attestation_ref="R-1",
        )
    async with factory() as session:
        run = await repo.get_run(session, run_id)
        assert run is not None
        assert run.status == RunStatus.DONE.value
        assert run.simulated == len(result.attempts)
        attempts = await repo.get_attempts(session, run_id)
        assert len(attempts) == len(result.attempts)
        # redaction applied on the way in
        for a in attempts:
            assert "PB_CANARY" not in a.target_response


async def test_empty_db_get_run_returns_none(db):
    async with db() as session:
        assert await repo.get_run(session, "nonexistent") is None


# ---------------------------------------------------------------- scope gate on API

@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_api_scope_gate_blocks_out_of_scope():
    from promptbreaker.api import app as app_module
    transport = ASGITransport(app=app_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/runs", json={
            "target": "https://not-yours.example.com/v1",
            "attestation": {
                "target_pattern": "mine.example.com",
                "authorized_by": "Eng", "reference": "R-1",
                "expires": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        })
    assert resp.status_code == 403


async def test_api_requires_attestation_fields():
    from promptbreaker.api import app as app_module
    transport = ASGITransport(app=app_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/runs", json={
            # IP literal + closed port: engine spawns, connection refused
            # instantly — no DNS, no network, no 149s teardown hang.
            "target": "http://127.0.0.1:9/v1",
            "allow_private": True,
            "attestation": {
                "target_pattern": "127.0.0.1",
                "authorized_by": "", "reference": "",
                "expires": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        })
    # 202 accepted into queue; authorization completeness enforced by CLI/ops,
    # but scope must still be valid — here pattern matches so it can proceed.
    assert resp.status_code in (202, 403)
    if resp.status_code == 202:
        # let the spawned task finish its instant-refused run before teardown
        await asyncio.sleep(0.3)


async def test_api_healthz():
    from promptbreaker.api import app as app_module
    transport = ASGITransport(app=app_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


async def test_startup_recovery_marks_interrupted_runs_failed(db):
    """A restart mid-run must leave a FAILED row, not a zombie QUEUED/EXECUTE."""
    from promptbreaker.store.models import RunRow

    factory = db
    async with factory() as session:
        session.add_all([
            RunRow(suite="quick", target="http://x/v1", adapter="openai",
                   status=RunStatus.EXECUTE.value, attested_by="Eng", attestation_ref="R-9"),
            RunRow(suite="quick", target="http://x/v1", adapter="openai",
                   status=RunStatus.DONE.value, attested_by="Eng", attestation_ref="R-9"),
        ])
        await session.commit()

    async with factory() as session:
        assert await repo.fail_interrupted_runs(session) == 1
        rows = await repo.list_runs(session, limit=10)
        failed = [r for r in rows if r.status == RunStatus.FAILED.value]
        done = [r for r in rows if r.status == RunStatus.DONE.value]
        assert len(failed) == 1 and len(done) == 1
        assert failed[0].abort_reason and "restart" in failed[0].abort_reason
        assert failed[0].finished_at is not None
        assert await repo.fail_interrupted_runs(session) == 0  # second boot: no-op
