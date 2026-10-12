"""Hermetic test environment.

The deployment .env (API keys, production HMAC key, prod DB path) must NEVER
leak into tests — real env vars take precedence over dotenv values in
pydantic-settings, so setting them here, before any promptbreaker import,
pins the test world:
  - no API keys (dev-mode auth) unless a test opts in explicitly
  - the dev HMAC key the engine tests verify chains against
  - a throwaway per-session database, never data/promptbreaker.db
  - no LLM judge (no network in tests; prefilter decides)
"""

from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="pb-test-")
os.environ["PB_API_KEYS"] = ""
os.environ["PB_DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP}/test.db"
os.environ["PB_EVIDENCE_HMAC_KEY"] = "dev-only-hmac-key-rotate-in-prod"
os.environ["PB_LLM_JUDGE_ENABLED"] = "false"
os.environ["PB_ALLOW_PRIVATE_TARGETS"] = "false"

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
async def _api_db():
    """Give API tests a schema-backed store, isolated per test.

    The engine is created lazily per test loop; disposing it afterwards
    closes this test's pooled connections so the next test's loop starts
    clean (aiosqlite connections are loop-affine once used).
    """
    from promptbreaker.store import db as dbmod
    await dbmod.init_db()
    yield
    if dbmod._engine is not None:
        await dbmod._engine.dispose()
