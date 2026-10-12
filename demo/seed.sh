#!/usr/bin/env bash
# Seed the PromptBreaker API with real scan history for demos.
#
# Starts the fake target (if needed), registers it as a target, then runs
# N core-suite scans through the real engine API and waits for each to
# finish. Everything the dashboard shows afterwards is genuine engine output.
#
# Usage:  ./demo/seed.sh [runs=2]
# Env:    API=http://127.0.0.1:8000   KEY=<plaintext api key from .api_key>
set -euo pipefail

cd "$(dirname "$0")/.."

API="${API:-http://127.0.0.1:8000}"
RUNS="${1:-2}"
KEY="${KEY:-$(sed -n 's/^PLAINTEXT_API_KEY=//p' .api_key 2>/dev/null || true)}"

py() { [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3; }

auth=(-H "Content-Type: application/json")
if [ -n "$KEY" ]; then auth+=(-H "x-api-key: $KEY"); fi

echo "==> waiting for API at $API"
for i in $(seq 1 30); do
  curl -fsS "$API/healthz" >/dev/null 2>&1 && break
  [ "$i" = 30 ] && { echo "API not reachable — start promptbreaker-api first"; exit 1; }
  sleep 1
done

echo "==> ensuring fake target on 127.0.0.1:18080"
if ! curl -fsS -o /dev/null -X POST http://127.0.0.1:18080/v1/chat/completions \
    -H 'Content-Type: application/json' -d '{"messages":[{"content":"ping"}]}' 2>/dev/null; then
  nohup "$(py)" demo/fake_target.py >/tmp/pb-fake-target.log 2>&1 &
  sleep 1
fi

echo "==> registering target"
EXISTING=$(curl -fsS "${auth[@]}" "$API/v1/targets" || echo '[]')
if echo "$EXISTING" | grep -q '127.0.0.1:18080'; then
  echo "    target already registered"
else
  curl -fsS "${auth[@]}" -X POST "$API/v1/targets" -d '{
    "name": "Local Demo Target",
    "adapter": "openai",
    "endpoint": "http://127.0.0.1:18080/v1",
    "secretRef": "env:DEMO_TARGET_KEY",
    "allowPrivate": true,
    "verified": true
  }' >/dev/null
  echo "    target added"
fi

for n in $(seq 1 "$RUNS"); do
  echo "==> starting scan $n/$RUNS"
  RESP=$(curl -fsS "${auth[@]}" -X POST "$API/v1/runs" -d "{
    \"target\": \"http://127.0.0.1:18080/v1\",
    \"adapter\": \"openai\",
    \"suite\": \"core\",
    \"allowPrivate\": true,
    \"attestation\": {
      \"target_pattern\": \"127.0.0.1\",
      \"authorized_by\": \"demo-seed\",
      \"reference\": \"DEMO-LOCAL-$n\",
      \"expires\": \"$(date -u -d '+1 day' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v+1d +%Y-%m-%dT%H:%M:%SZ)\"
    }
  }")
  RUN_ID=$(echo "$RESP" | "$(py)" -c 'import sys,json;print(json.load(sys.stdin)["runId"])')
  echo "    runId=$RUN_ID — waiting"
  for i in $(seq 1 120); do
    ST=$(curl -fsS "${auth[@]}" "$API/v1/runs/$RUN_ID" | "$(py)" -c 'import sys,json;print(json.load(sys.stdin)["status"])')
    case "$ST" in
      DONE|FAILED|CANCELED) echo "    status=$ST"; break ;;
    esac
    sleep 2
  done
done

echo "==> seed complete — open the dashboard and refresh Overview"
curl -fsS "${auth[@]}" "$API/v1/overview" | "$(py)" -m json.tool | head -20
