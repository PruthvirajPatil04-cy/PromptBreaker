"""Contract tests: the API's JSON keys must match dashboard/lib/types.ts.

These assertions are the permanent guard against snake_case drift. If a
field here fails, the dashboard will silently break — fix the API, not the
test, unless you also change types.ts.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from httpx import ASGITransport, AsyncClient

from promptbreaker.api import app as app_module


def _client():
    return AsyncClient(transport=ASGITransport(app=app_module.app), base_url="http://test")


async def test_overview_keys_match_typescript_contract():
    async with _client() as c:
        resp = await c.get("/v1/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"overall", "recentRuns", "suitesByCategory"}
    assert set(body["overall"]) == {
        "score", "band", "simulated", "successful", "categories", "lastRunAt", "trend"}
    for run in body["recentRuns"]:
        assert set(run) == {
            "runId", "name", "executedOn", "probes",
            "passed", "failed", "errors", "progressPct", "status", "source"}
        break
    for group in body["suitesByCategory"]:
        assert set(group) == {"category", "score", "suites"}
        for s in group["suites"]:
            assert set(s) == {
                "suiteId", "name", "category", "executedOn",
                "status", "passed", "failed", "errors"}
            break
        break


async def test_probes_keys_match_typescript_contract():
    async with _client() as c:
        resp = await c.get("/v1/probes")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 12  # Day-1 core suite
    for p in body:
        assert set(p) == {
            "id", "name", "category", "owasp",
            "enabled", "severity", "weight", "tags"}


async def test_compliance_keys_match_typescript_contract():
    async with _client() as c:
        resp = await c.get("/v1/compliance")
    assert resp.status_code == 200
    body = resp.json()
    frameworks = {c["framework"] for c in body}
    assert frameworks == {"OWASP-LLM", "NIST-AI-RMF"}
    for c in body:
        assert set(c) == {
            "id", "framework", "title", "coveragePct", "status", "linkedFindingIds"}
        assert c["status"] in ("pass", "partial", "gap")


async def test_targets_keys_match_typescript_contract():
    async with _client() as c:
        resp = await c.get("/v1/targets")
    assert resp.status_code == 200
    for t in resp.json():
        assert set(t) == {
            "id", "name", "adapter", "endpoint", "secretRef",
            "allowPrivate", "maxRedirects", "sandbox", "verified"}


async def test_hardening_keys_match_typescript_contract():
    async with _client() as c:
        resp = await c.get("/v1/hardening")
    assert resp.status_code == 200
    # empty DB → empty list, not an error
    assert resp.json() == []


async def test_create_run_returns_camel_case_run_id():
    async with _client() as c:
        resp = await c.post("/v1/runs", json={
            "target": "http://127.0.0.1:9/v1",
            "allow_private": True,
            "attestation": {
                "target_pattern": "127.0.0.1",
                "authorized_by": "QA", "reference": "R-42",
                "expires": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            },
        })
    assert resp.status_code == 202
    body = resp.json()
    assert set(body) == {"runId", "status", "eventsUrl"}
    assert body["runId"].startswith("run-")


async def test_run_detail_keys_match_typescript_contract():
    async with _client() as c:
        created = await c.post("/v1/runs", json={
            "target": "http://127.0.0.1:9/v1",
            "allow_private": True,
            "attestation": {
                "target_pattern": "127.0.0.1",
                "authorized_by": "QA", "reference": "R-43",
                "expires": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            },
        })
        run_id = created.json()["runId"]
        import asyncio
        await asyncio.sleep(0.5)  # let the engine finish its refused-connection run
        resp = await c.get(f"/v1/runs/{run_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {
        "runId", "name", "status", "target", "adapter", "suite", "executedOn",
        "score", "band", "simulated", "successful",
        "categories", "budget", "findings", "evidenceChainValid"}
    assert set(body["budget"]) == {"probes", "tokens", "costUsd"}
    for slot in body["budget"].values():
        assert set(slot) == {"used", "cap"}


async def test_events_json_is_array_of_log_events():
    async with _client() as c:
        created = await c.post("/v1/runs", json={
            "target": "http://127.0.0.1:9/v1",
            "allow_private": True,
            "attestation": {
                "target_pattern": "127.0.0.1",
                "authorized_by": "QA", "reference": "R-44",
                "expires": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            },
        })
        run_id = created.json()["runId"]
        import asyncio
        await asyncio.sleep(0.5)
        resp = await c.get(f"/v1/runs/{run_id}/events")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list) and len(body) > 0
    for e in body:
        assert set(e) == {"seq", "runId", "type", "ts", "level", "probeId", "detail"}
        assert e["level"] in ("info", "warn", "error")


async def test_empty_db_overview_returns_zeros_not_errors():
    # earlier tests in this session persisted runs — clear them so this
    # really exercises the empty-store path
    from sqlalchemy import delete

    from promptbreaker.store import db as dbmod
    from promptbreaker.store.models import RunRow
    async with dbmod.get_session_factory()() as session:
        await session.execute(delete(RunRow))
        await session.commit()

    async with _client() as c:
        resp = await c.get("/v1/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall"]["simulated"] == 0
    assert body["recentRuns"] == []
