#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-localhost}"
PORT="${PORT:-8000}"

curl -sS -X POST "http://${HOST}:${PORT}/ingest" \
  -H "Content-Type: application/json" \
  -d '{"source":{"bucket":"screenoteka","object_key":"010W7A4H1Ob3Yq9It172nj_c2e570aa4788d45b6a95ed58a070cd36_yanavi_prodd.webp"}}' \
  | python -m json.tool
