"""FastAPI control plane.

Endpoints are thin: they validate, delegate to the engine/queue, and stream
events from the append-only log. SSE replays from Last-Event-ID so reconnects
never lose events. Auth is API-key (sha256-compared, constant-time).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from promptbreaker import __version__

log = logging.getLogger("promptbreaker.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the store on boot so a fresh deploy comes up with tables."""
    try:
        from promptbreaker.store.db import init_db
        await init_db()
        log.info("store initialized")
    except Exception as exc:  # noqa: BLE001 — don't hard-crash the API on DB hiccups
        log.warning("store init deferred: %s", exc)
    yield
from promptbreaker.adapters.base import build_adapter
from promptbreaker.config import settings
from promptbreaker.engine.events import event_log
from promptbreaker.engine.runner import Engine
from promptbreaker.errors import ScopeError
from promptbreaker.judge.core import LlmJudge
from promptbreaker.models import RunBudget, RunStatus, ScopeAttestation
from promptbreaker.report.render import to_json, to_markdown, to_sarif

app = FastAPI(
    title="PromptBreaker AI",
    version=__version__,
    description="Adversarial assessment engine for LLM applications (authorized testing only)",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# in-memory registry for the MVP; store/ persists runs in Postgres
_RUNS: dict[str, dict] = {}


# ---------------------------------------------------------------- auth

async def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not settings.api_keys:
        return  # dev mode — no keys configured
    digest = hashlib.sha256(x_api_key.encode()).hexdigest()
    for allowed in settings.api_keys.split(","):
        if hmac.compare_digest(digest, allowed.strip()):
            return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")


# ---------------------------------------------------------------- schemas

class AttestationIn(BaseModel):
    target_pattern: str
    authorized_by: str
    reference: str
    expires: datetime


class RunRequest(BaseModel):
    target: str
    adapter: str = "openai"
    model: str = "default"
    api_key: str = Field(default="", exclude=True)
    suite: str = "core"
    allow_private: bool = False
    seed: int = 0
    budget: RunBudget = Field(default_factory=RunBudget)
    attestation: AttestationIn


class ReportRequest(BaseModel):
    format: str = "json"  # json | md | sarif


# ---------------------------------------------------------------- routes

@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True, "version": __version__}


@app.post("/v1/runs", status_code=202, dependencies=[Depends(require_api_key)])
async def create_run(req: RunRequest) -> dict:
    attestation = ScopeAttestation(**req.attestation.model_dump())
    adapter = build_adapter(
        req.adapter, req.target, allow_private=req.allow_private,
        model=req.model, api_key=req.api_key,
    )

    engine = Engine(
        adapter=adapter, attestation=attestation, budget=req.budget,
        suite=req.suite,
        llm_judge=LlmJudge(settings.judge_base_url, settings.judge_api_key, settings.judge_model),
        seed=req.seed,
    )
    run_id = engine.run_id

    # quick pre-flight scope check so the caller gets 403 synchronously
    from urllib.parse import urlparse
    host = (urlparse(req.target).hostname or req.target).lower()
    if not attestation.is_valid(host):
        raise HTTPException(status_code=403, detail="target outside authorized scope")

    _RUNS[run_id] = {"status": RunStatus.QUEUED.value, "engine": engine, "result": None}

    async def _execute() -> None:
        _RUNS[run_id]["status"] = RunStatus.EXECUTE.value
        try:
            result = await engine.run()
            _RUNS[run_id]["result"] = result
            _RUNS[run_id]["status"] = result.status.value
        except ScopeError as exc:
            _RUNS[run_id]["status"] = RunStatus.REJECTED.value if hasattr(RunStatus, "REJECTED") else RunStatus.FAILED.value
            _RUNS[run_id]["error"] = str(exc)
        except Exception as exc:  # noqa: BLE001 — surface as run failure, not crash
            _RUNS[run_id]["status"] = RunStatus.FAILED.value
            _RUNS[run_id]["error"] = str(exc)[:500]

    asyncio.create_task(_execute())
    return {"run_id": run_id, "status": RunStatus.QUEUED.value,
            "events_url": f"/v1/runs/{run_id}/events"}


@app.get("/v1/runs", dependencies=[Depends(require_api_key)])
async def list_runs() -> dict:
    return {"runs": [
        {"run_id": rid, "status": data["status"]}
        for rid, data in _RUNS.items()
    ]}


@app.get("/v1/runs/{run_id}", dependencies=[Depends(require_api_key)])
async def get_run(run_id: str) -> dict:
    data = _RUNS.get(run_id)
    if not data:
        raise HTTPException(status_code=404, detail="run not found")
    out: dict = {"run_id": run_id, "status": data["status"]}
    if data.get("error"):
        out["error"] = data["error"]
    result = data.get("result")
    if result is not None:
        out["summary"] = {
            "score": result.score.score if result.score else None,
            "band": result.score.band.value if result.score else None,
            "attempts": len(result.attempts),
            "findings": len(result.findings),
            "budget": result.budget,
        }
    return out


@app.get("/v1/runs/{run_id}/events")
async def run_events(run_id: str, request: Request) -> EventSourceResponse:
    """SSE stream with Last-Event-ID replay — the log is the source of truth."""
    if run_id not in _RUNS:
        raise HTTPException(status_code=404, detail="run not found")

    last_id_header = request.headers.get("last-event-id", "")
    since = int(last_id_header) if last_id_header.isdigit() else 0

    async def generator():
        # 1) replay anything already logged
        for ev in event_log.since(run_id, since):
            yield {"id": str(ev.seq), "event": ev.type, "data": json.dumps(ev.payload, default=str)}

        # 2) live subscription until the run terminates
        queue: asyncio.Queue = asyncio.Queue()
        unsubscribe = event_log.subscribe(run_id, queue.put)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15.0)
                except TimeoutError:
                    yield {"event": "ping", "data": "{}"}
                    if _RUNS.get(run_id, {}).get("status") in (
                        RunStatus.DONE.value, RunStatus.FAILED.value, RunStatus.CANCELED.value,
                    ):
                        break
                    continue
                yield {"id": str(ev.seq), "event": ev.type, "data": json.dumps(ev.payload, default=str)}
                if ev.type == "run.finished":
                    break
        finally:
            unsubscribe()

    return EventSourceResponse(generator())


@app.post("/v1/runs/{run_id}/report", dependencies=[Depends(require_api_key)])
async def get_report(run_id: str, req: ReportRequest) -> dict:
    data = _RUNS.get(run_id)
    if not data or data.get("result") is None:
        raise HTTPException(status_code=409, detail="run not finished")
    result = data["result"]
    fmt = req.format
    body = {"json": to_json, "md": to_markdown, "markdown": to_markdown, "sarif": to_sarif}.get(fmt)
    if body is None:
        raise HTTPException(status_code=400, detail="format must be json|md|sarif")
    return {"run_id": run_id, "format": fmt, "report": body(result)}


@app.post("/v1/runs/{run_id}/cancel", dependencies=[Depends(require_api_key)])
async def cancel_run(run_id: str) -> dict:
    data = _RUNS.get(run_id)
    if not data:
        raise HTTPException(status_code=404, detail="run not found")
    data["status"] = RunStatus.CANCELED.value
    event_log.append(run_id, "run.finished", {"status": RunStatus.CANCELED.value})
    return {"run_id": run_id, "status": RunStatus.CANCELED.value}
