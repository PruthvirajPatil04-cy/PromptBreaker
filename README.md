# PromptBreaker AI

Adversarial assessment engine for LLM applications. Runs curated and generated
prompt-injection / jailbreak / data-exfiltration probes against authorized
targets, judges outcomes with a hybrid rule + LLM judge, and produces
evidence-backed reports (Markdown / JSON / SARIF).

> **Authorized testing only.** Every run requires an explicit scope attestation.
> See [ETHICAL_USE.md](ETHICAL_USE.md).

## Quick start (dev)

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/promptbreaker scan --target http://localhost:8001/v1 --adapter openai \
    --suite core --format json --output results.json --fail-on High
```

## Architecture

- `engine/` — LangGraph-style run state machine (plan → execute → judge → mutate → report), durable event log, hard budget caps
- `adapters/` — target adapters (HTTP, OpenAI-compatible, Ollama, MCP) behind one interface; all egress passes the SSRF guard
- `probes/` — curated probe registry (OWASP LLM Top 10 mapped)
- `judge/` — rule prefilter + LLM-as-judge with structured verdicts (no quoted span ⇒ verdict rejected)
- `report/` — MD / JSON / SARIF 2.1.0 with SHA-256 + HMAC-chained evidence
- `api/` — FastAPI + SSE (event log replay via Last-Event-ID)
- `dashboard/` — Next.js console (mock-first, contract-locked)

## Production notes

- `DATABASE_URL=postgresql+asyncpg://...` — same models, no code changes
- Swap the in-process queue for ARQ/Redis via `engine.queue` interface
- Target adapters are packaged for extraction into the outbound-only VPC runner
