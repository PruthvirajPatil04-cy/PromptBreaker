"""Runtime configuration loaded from environment (.env supported)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PB_", extra="ignore")

    # Storage — swap to postgresql+asyncpg://... in production, no code changes.
    database_url: str = "sqlite+aiosqlite:///./promptbreaker.db"

    # Judge / attack-generation model (OpenAI-compatible endpoint, e.g. vLLM or LiteLLM proxy).
    # Self-hosted by default — no provider ToS exposure.
    judge_base_url: str = "http://localhost:11434/v1"
    judge_api_key: str = "not-needed"
    judge_model: str = "qwen2.5:14b"
    # 0 disables the LLM judge entirely; prefilter-only mode.
    llm_judge_enabled: bool = True

    # Budgets (hard caps — the mutation loop MUST terminate).
    max_probes_per_run: int = 500
    max_mutations_per_probe: int = 8
    max_run_tokens: int = 2_000_000
    max_run_cost_usd: float = 25.0
    run_timeout_seconds: int = 1800
    # Parallel probe execution — semaphore-bounded fan-out inside one run.
    run_concurrency: int = 4

    # Evidence
    evidence_hmac_key: str = "dev-only-hmac-key-rotate-in-prod"
    evidence_ttl_days: int = 90

    # API
    api_host: str = "0.0.0.0"  # noqa: S104 — engine binds wide; auth + dashboard gate sit in front
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # Auth — API keys are hashed (sha256), never stored plaintext.
    # Entries are "sha256hex" (admin, default) or "sha256hex:viewer" (read-only).
    api_keys: str = ""  # comma-separated sha256 hex digests, optional ":role"

    # Alerts — Slack/Discord-compatible webhook fired when a run finishes with
    # High or Critical findings. Empty disables alerts.
    webhook_url: str = ""

    # Report branding — appears in Markdown/JSON/SARIF report headers.
    report_org: str = "PromptBreaker AI"
    report_title: str = ""

    # SSRF guard — private ranges blocked unless explicitly allowed per target.
    allow_private_targets: bool = False
    max_redirects: int = 3
    request_timeout_seconds: int = 60


settings = Settings()
