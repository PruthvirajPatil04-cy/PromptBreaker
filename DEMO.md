# PromptBreaker AI — Live Demo Runbook

Everything on the dashboard during the demo is real engine output. This
runbook gets you from a cold machine to a populated dashboard in ~3 minutes.

## Architecture (one paragraph for questions)

Split control plane / data plane. The **control plane** is the FastAPI service
(`/v1/...` endpoints) — it validates scope attestations, queues runs, and
serves the aggregated dashboard contract (camelCase, locked to
`dashboard/lib/types.ts` by contract tests). The **data plane** is the engine:
probe registry → hybrid judge (rule prefilter + optional LLM judge) →
HMAC-chained evidence → score. Runs persist to SQLite now, Postgres by
changing `PB_DATABASE_URL`. Deployment is two native systemd units — no
containers required.

## Services

| Unit | Port | Purpose |
|------|------|---------|
| `promptbreaker-api` | 8000 | FastAPI control plane + engine runs |
| `promptbreaker-dashboard` | 3000 | Next.js dashboard (live mode) |
| `demo/fake_target.py` | 18080 | Local OpenAI-shaped target being assessed |

```bash
systemctl status promptbreaker-api promptbreaker-dashboard
```

## First-time seed (populates real history)

```bash
cd ~/promptbreaker
./demo/seed.sh 2        # registers the local target, runs 2 real core scans
```

Each scan goes through the full engine: scope-attestation gate, 12 core
probes plus mutations, hybrid judging, evidence chaining, scoring. Expect
~20–60s per run depending on the box.

## Demo flow (what to click)

1. **Overview** — Overall Score gauge (real weighted score), Category Scores
   bars, Recent Test Runs (live progress bars while a run executes), and
   Categories Overview cards derived from actual attempt counts.
2. **New Test Run +** — the Start Scan modal. Fill Authorized by + Reference;
   the button stays disabled without them because the engine's scope gate
   rejects unattested runs. Submit → lands on Run Detail.
3. **Run Detail** — polls every 2s while the run is in flight: score,
   budget bars, categories, and findings fill in live. Findings expand to
   show OWASP mapping, judge engine, evidence SHA-256, rationale, and the
   verbatim quoted span (the hard rule: no verbatim evidence → no claim).
   **Download Report** produces the markdown report of a finished run.
4. **Log Analysis** — pick any run, hit **Start live tail** for SSE. Filter
   chips for info/warn/error; click an event to inspect its JSON payload.
5. **Probe Settings** — the 12-probe registry straight from the engine
   (id, category, OWASP LLM01–LLM10, severity, weight, tags).
6. **Compliance** — coverage percentages computed from real results; a
   control shows `gap` when its probes never ran or findings exist.
7. **Target Settings** — adapter config; secrets are references only
   (`env:...`), never plaintext.
8. **Prompt Hardening** — one before/after card per category that produced
   findings in the latest run.

## Verifying live mode (before the audience arrives)

```bash
# engine health
curl -s http://127.0.0.1:8000/healthz        # {"ok":true,...}

# auth enforced (401 without key, 200 with key from .api_key)
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/v1/overview
KEY=$(sed -n 's/^PLAINTEXT_API_KEY=//p' .api_key)
curl -s -H "x-api-key: $KEY" http://127.0.0.1:8000/v1/overview | head -c 300

# dashboard reachable from your LAN IP (share this URL)
curl -s -o /dev/null -w '%{http_code}\n' http://172.28.99.44:3000
```

The topbar badge must read **engine online**. If it says *engine offline*
the Overview shows an explicit "Engine unreachable" error — the dashboard
never fabricates numbers when the API is down.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Overview shows error banner | `systemctl status promptbreaker-api` |
| Runs stuck QUEUED | check API logs: `journalctl -u promptbreaker-api -n 50` |
| Scan returns 403 | attestation pattern doesn't match target host — the scope gate working as designed |
| Dashboard still shows old numbers | it polls every 3s while a run is active; refresh otherwise |
| Want a fresh demo dataset | stop API, `rm data/promptbreaker.db`, start API, rerun `./demo/seed.sh 3` |

## Security notes (say these out loud if asked)

- `NEXT_PUBLIC_PB_API_KEY` is baked into the client bundle — anyone with
  dev-tools on a demo machine can read it. That is acceptable for a LAN
  demo; for production the key must stay server-side (proxy the API through
  the Next.js server, or issue short-lived per-user tokens).
- `demo/fake_target.py` is a deliberately vulnerable stand-in for demos.
  Never point the engine at a system you are not authorized to test — the
  scope gate exists precisely to make that a hard error, not a policy.

## Reset / re-seed

```bash
sudo systemctl stop promptbreaker-api
rm -f ~/promptbreaker/data/promptbreaker.db
sudo systemctl start promptbreaker-api
cd ~/promptbreaker && ./demo/seed.sh 3
```

## Talking points

- **Scope attestation gate**: no attestation, no run. Authorization is part
  of the data model, not a wiki page.
- **Evidence chain**: every artifact SHA-256-hashed and HMAC-chained; the
  Run Detail badge shows `Valid ✓` or `BROKEN` — tampering is detectable.
- **Hard rule on findings**: a claim requires a verbatim quoted span from
  the target's own response. Judge rationale without evidence is rejected.
- **Budget tracker**: probes/tokens/cost caps abort runaway runs.
- **Fail loudly**: live mode never falls back to mock data (a fabricated
  number in a security demo is worse than an error banner).
- **Contract-locked frontend**: API responses are asserted field-for-field
  against the TypeScript types in `tests/test_api_contract.py` — 40 tests
  guard the whole surface.
