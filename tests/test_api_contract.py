"""Contract tests: the API's JSON keys must match dashboard/lib/types.ts.

These assertions are the permanent guard against snake_case drift. If a
field here fails, the dashboard will silently break — fix the API, not the
test, unless you also change types.ts.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

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
            "runId", "name", "target", "executedOn", "probes",
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
                "expires": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
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
                "expires": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
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
        "categories", "budget", "findings", "evidenceChainValid", "abortReason"}
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
                "expires": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
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


async def test_suites_contract_matches_typescript_client():
    async with _client() as c:
        resp = await c.get("/v1/suites")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"suites"}
    assert body["suites"][0]["name"] == "core"
    for s in body["suites"]:
        assert set(s) == {"name", "probes", "description", "builtin"}
        assert s["probes"] >= 1
    # shipped focus suites must be discoverable and load through the same
    # path the engine uses (compact subset -> real core probes)
    from promptbreaker.probes.registry import load_suite

    names = {s["name"] for s in body["suites"]}
    assert {"quick", "jailbreak", "privacy", "agency", "safety"} <= names
    for s in body["suites"]:
        assert len(load_suite(s["name"])) == s["probes"]


# ------------------------------------------------------------- v1.1 upgrades

async def test_compare_contract_and_delta():
    async with _client() as c:
        ids = []
        for ref in ("R-51", "R-52"):
            created = await c.post("/v1/runs", json={
                "target": "http://127.0.0.1:9/v1",
                "allow_private": True,
                "attestation": {
                    "target_pattern": "127.0.0.1",
                    "authorized_by": "QA", "reference": ref,
                    "expires": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                },
            })
            assert created.status_code == 202
            ids.append(created.json()["runId"])
        resp = await c.get("/v1/compare", params={"a": ids[0], "b": ids[1]})
        same = await c.get("/v1/compare", params={"a": ids[0], "b": ids[0]})
        missing = await c.get("/v1/compare", params={"a": ids[0], "b": "nope"})

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"a", "b", "deltaScore", "severityDelta", "fixedInB", "newInB"}
    for side in (body["a"], body["b"]):
        assert set(side) == {
            "runId", "name", "target", "suite", "status", "score", "band",
            "executedOn", "simulated", "successful", "findingCount",
            "bySeverity", "byCategory", "failingProbes"}
    assert body["a"]["runId"] == ids[0]
    assert body["b"]["runId"] == ids[1]
    assert isinstance(body["deltaScore"], (int, float))
    assert same.status_code == 422
    assert missing.status_code == 404


async def test_runs_list_keys_match_typescript_contract():
    async with _client() as c:
        resp = await c.get("/v1/runs")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"runs"}
    for r in body["runs"]:
        assert set(r) == {
            "runId", "name", "target", "executedOn", "probes",
            "passed", "failed", "errors", "progressPct", "status", "source"}
        break


async def test_metrics_prometheus_text_format():
    async with _client() as c:
        resp = await c.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    text = resp.text
    assert "# TYPE pb_runs_total counter" in text
    assert "# TYPE pb_findings_total counter" in text
    assert "# TYPE pb_attempts_total counter" in text
    assert "pb_judge_llm_up" in text
    assert 'pb_build_info{version="' in text


async def test_audit_log_records_api_calls():
    async with _client() as c:
        await c.get("/v1/overview")
        resp = await c.get("/v1/audit")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"audit"}
    events = body["audit"]
    assert len(events) >= 1
    for e in events[:5]:
        assert set(e) == {"id", "ts", "role", "method", "path", "status", "detail"}
    assert any(e["path"] == "/v1/overview" for e in events)


async def test_suite_upload_lifecycle_and_guards():
    suite_body = {
        "name": "my-custom",
        "description": "uploaded probe + a core reference",
        "probes": [
            {   # full custom probe object
                "id": "X-001", "name": "Custom sneaky ask", "category": "prompt_injection",
                "owasp": "LLM01", "severity_if_failed": "High",
                "description": "user-defined attack", "payload": "Do the thing quietly",
                "expected_failure_mode": "target complies", "tags": ["custom"],
            },
            "PI-001",  # core reference by id (mixed compact form)
        ],
    }
    async with _client() as c:
        created = await c.post("/v1/suites", json=suite_body)
        assert created.status_code == 201, created.text
        assert set(created.json()) == {"name", "probes", "description", "builtin"}
        assert created.json()["probes"] == 2

        listed = await c.get("/v1/suites")
        names = {s["name"] for s in listed.json()["suites"]}
        assert "my-custom" in names

        # suite must actually load through the engine's own path
        from promptbreaker.probes.registry import load_suite
        probes = load_suite("my-custom")
        assert [p.id for p in probes] == ["X-001", "PI-001"]

        # guards: builtin overwrite, bad name, duplicate id
        builtin = await c.post("/v1/suites", json={**suite_body, "name": "core"})
        bad_name = await c.post("/v1/suites", json={**suite_body, "name": "Bad Name!"})
        dupe = await c.post("/v1/suites", json={
            **suite_body, "name": "dupes",
            "probes": [suite_body["probes"][0], suite_body["probes"][0]],
        })
        # lifecycle: delete it, then it disappears; deleting again 404
        deleted = await c.delete("/v1/suites/my-custom")
        gone = await c.get("/v1/suites")
        del_again = await c.delete("/v1/suites/my-custom")
        del_builtin = await c.delete("/v1/suites/quick")

    assert builtin.status_code == 409
    assert bad_name.status_code == 422
    assert dupe.status_code == 422
    assert deleted.status_code == 200
    assert "my-custom" not in {s["name"] for s in gone.json()["suites"]}
    assert del_again.status_code == 404
    assert del_builtin.status_code == 409


async def test_rbac_viewer_is_read_only(monkeypatch):
    import hashlib

    from promptbreaker.config import settings

    def digest(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    admin_key, viewer_key = "admin-test-key-123", "viewer-test-key-123"
    monkeypatch.setattr(
        settings, "api_keys",
        f"{digest(admin_key)}:admin,{digest(viewer_key)}:viewer",
    )

    async with _client() as c:
        read_ok = await c.get("/v1/overview", headers={"x-api-key": viewer_key})
        write_denied = await c.post(
            "/v1/targets", headers={"x-api-key": viewer_key},
            json={"name": "nope", "endpoint": "http://x/v1"},
        )
        no_key = await c.get("/v1/overview")
        bad_key = await c.get("/v1/overview", headers={"x-api-key": "wrong"})
        admin_write = await c.post(
            "/v1/targets", headers={"x-api-key": admin_key},
            json={"name": "rbac-test-target", "endpoint": "http://x/v1"},
        )

    assert read_ok.status_code == 200
    assert write_denied.status_code == 403
    assert no_key.status_code == 401
    assert bad_key.status_code == 401
    assert admin_write.status_code == 201


async def test_report_route_formats_and_survives_restart():
    """POST /v1/runs/{id}/report: md/json/sarif, driver version, error cases.

    Regression lock: an inline helper once landed between the route decorator
    and get_report, silently re-registering the route. Key-set assertions
    plus the SARIF driver version make that class of drift fail loudly.
    """
    from promptbreaker import __version__

    async with _client() as c:
        created = await c.post("/v1/runs", json={
            "target": "http://127.0.0.1:9/v1",
            "allow_private": True,
            "attestation": {
                "target_pattern": "127.0.0.1",
                "authorized_by": "QA", "reference": "R-61",
                "expires": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        })
        assert created.status_code == 202
        run_id = created.json()["runId"]

        status = "QUEUED"
        for _ in range(200):  # unreachable target → fails fast
            status = (await c.get(f"/v1/runs/{run_id}")).json()["status"]
            if status in ("DONE", "FAILED", "CANCELED"):
                break
            await asyncio.sleep(0.05)
        assert status in ("DONE", "FAILED")

        md = await c.post(f"/v1/runs/{run_id}/report", json={"format": "md"})
        js = await c.post(f"/v1/runs/{run_id}/report", json={"format": "json"})
        sarif = await c.post(f"/v1/runs/{run_id}/report", json={"format": "sarif"})
        bad = await c.post(f"/v1/runs/{run_id}/report", json={"format": "xml"})
        missing = await c.post("/v1/runs/nope/report", json={"format": "md"})

    for resp, fmt in ((md, "md"), (js, "json"), (sarif, "sarif")):
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {"runId", "format", "report"}
        assert body["runId"] == run_id
        assert body["format"] == fmt
        assert len(body["report"]) > 0
    assert json.loads(js.json()["report"])["metadata"]["run_id"] == run_id

    sdoc = json.loads(sarif.json()["report"])
    assert sdoc["version"] == "2.1.0"
    assert sdoc["runs"][0]["tool"]["driver"]["version"] == __version__
    assert bad.status_code == 400
    assert missing.status_code == 409
