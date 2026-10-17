#!/usr/bin/env bash
# PromptBreaker OFFLINE Windows bundle — builds the fully self-contained
# desktop app from Linux: embeddable CPython 3.12 + win_amd64 wheels (engine
# + demo chatbots), node.exe (Next standalone dashboard), Go launcher, zip +
# per-user NSIS installer. No WSL services, no tunnel, no internet required
# on the target machine; the LLM judge auto-detects a local Ollama and
# degrades to the deterministic prefilter when absent.
#
# Output:  windows/dist-offline/PromptBreaker-Offline-win64.zip
#          windows/dist-offline/PromptBreaker-Offline-Setup.exe
#
# Downloads are cached in ~/.cache/pb-offline (rebuilds are offline-fast).
set -euo pipefail
cd "$(dirname "$0")/.."                      # repo root

PY_VER=3.12.8
NODE_VER=v20.18.1
CACHE="${PB_OFFLINE_CACHE:-$HOME/.cache/pb-offline}"
OFF=windows/offline
DIST=windows/dist-offline
RT=$OFF/runtime
VENV_PY=.venv/bin/python

mkdir -p "$CACHE/wheels" "$DIST"
rm -rf "$OFF"
mkdir -p "$RT/python/Lib/site-packages" "$OFF/app" "$RT/dashboard"

# --- 1. embeddable CPython (win_amd64) ---------------------------------------
PYZIP="$CACHE/python-$PY_VER-embed-amd64.zip"
[ -f "$PYZIP" ] || curl -fsSL -o "$PYZIP" \
  "https://www.python.org/ftp/python/$PY_VER/python-$PY_VER-embed-amd64.zip"
unzip -qo "$PYZIP" -d "$RT/python"
# The embeddable build has no pip and no automatic site-packages; list our
# wheel dir on the module path so `python -m uvicorn` finds everything.
cat > "$RT/python/python312._pth" <<'PYPATH'
python312.zip
.
Lib\site-packages
import site
PYPATH

# --- 2. win_amd64 wheels (engine dependency closure, cp312) ------------------
if ! ls "$CACHE/wheels"/*.whl >/dev/null 2>&1; then
  "$VENV_PY" -m pip download -q -d "$CACHE/wheels" \
    --platform win_amd64 --python-version 3.12 --implementation cp --abi cp312 \
    --only-binary=:all: \
    fastapi uvicorn sse-starlette "sqlalchemy[asyncio]" aiosqlite \
    pydantic pydantic-settings httpx pyyaml
fi
for w in "$CACHE"/wheels/*.whl; do
  unzip -qo "$w" -d "$RT/python/Lib/site-packages"
done

# --- 3. the promptbreaker package itself (suites + golden set included) ------
rm -rf "$RT/python/Lib/site-packages/promptbreaker"
cp -r src/promptbreaker "$RT/python/Lib/site-packages/promptbreaker"
find "$RT/python/Lib/site-packages/promptbreaker" -name __pycache__ -type d -exec rm -rf {} +

# --- 4. node.exe (drives the Next standalone dashboard) ----------------------
NODEZIP="$CACHE/node-$NODE_VER-win-x64.zip"
[ -f "$NODEZIP" ] || curl -fsSL -o "$NODEZIP" \
  "https://nodejs.org/dist/$NODE_VER/node-$NODE_VER-win-x64.zip"
unzip -p "$NODEZIP" "node-$NODE_VER-win-x64/node.exe" > "$RT/node.exe"

# --- 5. demo chatbots (pure stdlib — run in the bundled python) --------------
cp demo/chatbots.py "$OFF/app/chatbots.py"

# --- 6. offline API key: fresh per bundle (never the hosted key) -------------
OFFLINE_KEY="pb_offline_$(head -c16 /dev/urandom | od -An -tx1 | tr -d ' \n')"
printf '%s' "$OFFLINE_KEY" > "$RT/api.key"

# --- 7. dashboard: Next standalone build (offline env, fresh key baked) ------
echo "[offline] building dashboard (standalone, offline key)..."
(cd dashboard && rm -rf .next \
  && NEXT_PUBLIC_PB_USE_MOCK=false NEXT_PUBLIC_PB_API_BASE= \
     NEXT_PUBLIC_PB_API_KEY="$OFFLINE_KEY" \
     npx next build >/dev/null)
mkdir -p "$RT/dashboard/.next"
cp -r dashboard/.next/standalone/. "$RT/dashboard/"
cp -r dashboard/.next/static "$RT/dashboard/.next/static"

# --- 8. Go launcher (offline detection is runtime behavior — same binary) ----
(cd windows && GOOS=windows GOARCH=amd64 CGO_ENABLED=0 \
  go build -trimpath -ldflags="-s -w -H windowsgui" -o "offline/PromptBreaker.exe" .)
cp windows/README-OFFLINE.txt "$OFF/README.txt"
cat > "$OFF/config.json" <<'JSON'
{
  "dashboardUrl": "http://127.0.0.1:3000",
  "publicUrl": ""
}
JSON

# --- 9. restore the hosted/service dashboard build ---------------------------
echo "[offline] rebuilding dashboard for the service..."
(cd dashboard && rm -rf .next \
  && NEXT_PUBLIC_PB_USE_MOCK=false NEXT_PUBLIC_PB_API_BASE= \
     NEXT_PUBLIC_PB_API_KEY="$(cat ../.api_key)" \
     npx next build >/dev/null \
  && chown -R cyberex:cyberex .next)
if systemctl exists promptbreaker-dashboard 2>/dev/null; then
  systemctl restart promptbreaker-dashboard
fi

# --- 10. artifacts -----------------------------------------------------------
echo "[offline] zipping..."
REPO_ROOT="$(pwd)"
(cd "$OFF" && rm -f "$REPO_ROOT/$DIST/PromptBreaker-Offline-win64.zip" \
  && zip -qr "$REPO_ROOT/$DIST/PromptBreaker-Offline-win64.zip" \
       PromptBreaker.exe config.json README.txt runtime app)
echo "[offline] NSIS installer..."
(cd windows && makensis -V2 PromptBreaker-Offline.nsi >/dev/null)

ls -la "$DIST"
echo "[offline] bundle: $DIST (api key: $OFFLINE_KEY)"
