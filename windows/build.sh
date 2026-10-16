#!/usr/bin/env bash
# Builds the Windows desktop app from Linux: icon resources -> PE exe -> NSIS
# installer. Run from the windows/ directory.
set -euo pipefail
cd "$(dirname "$0")"

export CGO_ENABLED=0 GOOS=windows GOARCH=amd64 GOFLAGS=-mod=mod
WINRES="${WINRES:-$HOME/go/bin/go-winres}"
[ -x "$WINRES" ] || go install github.com/tc-hib/go-winres@latest

"$WINRES" make --arch amd64
mkdir -p dist
go build -trimpath -ldflags "-s -w -H windowsgui" -o dist/PromptBreaker.exe .
makensis PromptBreaker.nsi
echo "--- artifacts:"
file dist/* | sed 's/^/  /'
ls -la dist
