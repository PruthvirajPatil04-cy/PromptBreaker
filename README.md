# PromptBreaker AI

[![CI](https://github.com/PruthvirajPatil04-cy/PromptBreaker/actions/workflows/ci.yml/badge.svg)](https://github.com/PruthvirajPatil04-cy/PromptBreaker/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-14B8A6)](https://www.python.org)
[![License Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

Adversarial assessment engine for LLM applications. Fires curated and mutated
prompt-injection / jailbreak / data-exfiltration probes at **authorized**
targets, judges every outcome with a two-stage hybrid judge, and ships
evidence-backed reports (Markdown / JSON / SARIF 2.1.0) with SHA-256 +
HMAC-chained artifacts.

> **Authorized testing only.** Every run requires an explicit scope
> attestation; the engine refuses targets outside it. See
> [ETHICAL_USE.md](ETHICAL_USE.md).

## Why PromptBreaker

| | PromptBreaker | garak | PyRIT | Promptfoo |
|---|---|---|---|---|
| Primary focus | Adversarial probe engine **+ full assessment console** | LLM vulnerability scanner | red-teaming **framework** (code) | LLM eval / regression **CI** |
| Judge | Two-stage: deterministic prefilter → local LLM judge, **quoted-span verification kills hallucinated findings** | classifier plugins | iterative attack with model-backed scorers | grader prompts / custom logic |
| Evidence integrity | SHA-256 + HMAC-chained per attempt, tamper-evident reports | — | — | — |
| Scope safety | Mandatory scope attestation + SSRF guard (no accidental internal scans) | target config | implicit | implicit |
| Reporting | Markdown, JSON, **SARIF 2.1.0** (GitHub code scanning upload) | reports | — | JSON/CSV |
| Ops surface | REST + SSE, **RBAC keys, audit log, Prometheus /metrics, webhooks, run-vs-run compare** | CLI | library | CLI + CI |
| Live demo | 8 deliberately vulnerable chatbots + mutation-proof selftest | — | — | — |
| Deployment | pip, **Docker Compose**, GHCR images, **Windows WebView2 app (NSIS installer)** | pip | pip | npm |

It answers a question the others leave open: *"we patched the prompt — prove
it got safer."* Run before → harden → run after → **Compare Runs** shows the
score delta, the severity delta, and exactly which probes were fixed or
regressed.

## Quick start

### pip

```bash
git clone https://github.com/PruthvirajPatil04-cy/PromptBreaker.git
cd PromptBreaker && pip install .
promptbreaker scan --target https://api.yourapp.com/v1 --adapter openai \
  --api-key $TARGET_API_KEY --suite core --fail-on High --format sarif \
  --output promptbreaker.sarif --attested-by "SecTeam <sec@co>" --attestation-ref ENG-42
```

### Docker Compose (dashboard + engine + optional local judge)

```bash
docker compose up -d                  # console on :3000, engine on :8000
docker compose --profile judge up -d  # + local Ollama judge (fully offline)
```

### Config-file scan (CI-native)

`promptbreaker.yml` next to your code — CLI flags always override it, secrets
come from env (`api_key_env`), never from the file:

```bash
promptbreaker scan --config examples/promptbreaker.yml
echo $?   # 0 clean · 1 findings ≥ fail_on · 2 engine error
```

Copy
[`examples/promptbreaker-example.yml`](examples/promptbreaker-example.yml)
into your project to gate every PR and upload SARIF to GitHub code scanning.

### Windows app

`windows/dist/PromptBreaker-Setup.exe` — native WebView2 wrapper around the
console; connects to localhost, the hosted demo, or shows offline help.
Credential config lives in `config.json` next to the exe.

## The judge — why the verdicts are defensible

```
target response ──▶ deterministic prefilter ──decides──▶ verdict + rationale
                          │ rules abstain (evasive target)
                          ▼
                   local LLM judge (Ollama, offline)
                          │ structured verdict + quoted span
                          ▼
                span MUST be a verbatim substring of the response
                else the verdict is rejected — no hallucinated findings
```

- The prefilter is signature-driven and deterministic: refusal markers,
  compliance patterns, secret shapes (live `sk-…`, emails, `password:`),
  canary echo, judge-manipulation detection.
- Judge-prompt-injection attempts inside target responses are flagged and can
  never steer a verdict.
- Demo selftest (`python demo/chatbots.py --selftest`) verifies
  **672 bot × probe × mutator combinations** still produce the designed
  verdicts — judge determinism is regression-tested before every demo.

## API surface (v1.2)

| Endpoint | Purpose |
|---|---|
| `POST /v1/runs` · `GET /v1/runs/{id}` · `GET /v1/runs/{id}/events` | start / inspect / stream runs (SSE, `Last-Event-ID` replay) |
| `POST /v1/runs/{id}/resume` | **resume a FAILED/CANCELED run** — re-plans only the probes that never executed, links back via `resumedFrom` |
| `POST /v1/runs/{id}/report` | report as `json` / `md` / **`sarif`** (branded via `PB_REPORT_ORG` / `PB_REPORT_TITLE`) |
| `GET /v1/compare?a=&b=` | **run-vs-run delta** — score, severity, fixed/new probes |
| `GET/POST/DELETE /v1/suites` | suite picker + **custom suite upload** (your probes + core refs; built-ins protected) |
| `POST /v1/targets/{id}/verify` | **pre-stage health check** — one harmless round-trip, never a probe |
| `GET/POST/DELETE /v1/keys` | **issue RBAC keys** — sha256 stored, plaintext returned once, revoke takes effect immediately |
| `PATCH /v1/findings/{id}` | **triage** a finding: open / accepted_risk / false_positive / patched |
| `GET /v1/review` | **review queue** — open Critical/High findings awaiting a human call |
| `GET/POST/PATCH/DELETE /v1/schedules` | **scheduled scans** — each carries its own attestation; expiry stops firing |
| `GET /v1/audit` | **audit log** of every authenticated API call |
| `GET /metrics` | Prometheus: runs/findings/attempts counters, review queue depth, schedule states, judge liveness |
| `GET /v1/overview` · `/v1/probes` · `/v1/compliance` · `/v1/hardening` | console data |

**Engine v1.2:** parallel probe execution (default 4 concurrent slots,
order-preserving), stateful **multi-turn attack chains** (`multiturn` suite —
setup → escalate → extract, judged on the final turn), **adaptive mutation**
(unexplored mutators run first, per-target stats persisted), incremental
attempt persistence (a crash keeps every judged probe), and a hardened
`systemContext` override so the **hardening wizard** can re-scan with the
actual patched prompt injected.

**RBAC:** API keys are sha256 hashes (`hash` = admin, `hash:viewer` =
read-only). Keys issued from the dashboard (`/v1/keys`) are `pbk_…` — the
plaintext is shown exactly once. Viewers can read and download reports; only
admins can start scans, manage targets, keys, or schedules. Every call is
audited.

**Alerts:** set `PB_WEBHOOK_URL` (Slack/Discord-compatible) — runs that land
High/Critical findings fire a webhook with score, band, and counts.

**Judge calibration:** `src/promptbreaker/judge/golden.jsonl` locks 16 golden
cases in CI (`tests/test_judge_calibration.py`); run
`.venv/bin/python scripts/calibrate_judge.py` against the live judge model to
measure the LLM half (ship threshold: ≥70%).

## Architecture

- `engine/` — run state machine (plan → execute → judge → mutate → report),
  durable append-only event log, hard budget caps, cancellable
- `adapters/` — OpenAI-compatible / Ollama / raw HTTP behind one interface;
  all egress passes the SSRF guard (DNS-rebinding-aware, redirect-checked)
- `probes/` — curated registry mapped to OWASP LLM Top 10; suites are data
  (JSON), not code — including your uploaded ones
- `judge/` — prefilter + LLM-as-judge with structured, span-verified verdicts
- `security/` — redaction (captured transcripts routinely contain real keys),
  HMAC evidence chain, scope attestation
- `report/` — MD / JSON / SARIF 2.1.0
- `api/` — FastAPI + SSE, RBAC, audit, metrics, webhooks
- `dashboard/` — Next.js console (contract-locked to the API by
  `tests/test_api_contract.py` — drift breaks CI, not the demo)
- `demo/` — 8 vulnerable chatbots (hardened → leaking → evasive-judge bot)
- `windows/` — WebView2 wrapper + NSIS installer

## Development

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests/ -q        # contract + engine + security suites
.venv/bin/python demo/chatbots.py --selftest # 672-combo judge determinism check

cd dashboard && npm ci && npm run dev        # console on :3000
```

Demo targets: `python demo/chatbots.py` serves SecureBot…CreativeAI on
18081–18087 plus EvasiveBot on 18088 (its replies evade every signature, so
the **LLM judge decides live on stage**).
