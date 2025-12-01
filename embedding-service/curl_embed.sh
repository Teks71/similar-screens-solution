#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-localhost}"
PORT="${PORT:-8001}"
# Hardcoded test object for quick manual runs
BUCKET="${BUCKET:-similar-screens-input}"
KEY="${KEY:-AQADiAxrGz2raUl-.jpg}"

curl -sS -X POST "http://${HOST}:${PORT}/embed" \
  -H "Content-Type: application/json" \
  -d "{\"source\":{\"bucket\":\"${BUCKET}\",\"object_key\":\"${KEY}\"}}" \
  | python -m json.tool
