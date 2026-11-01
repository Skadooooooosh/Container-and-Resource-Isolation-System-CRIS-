#!/usr/bin/env bash
# API (no cgroup delegation: namespaces + monitoring work, limits report "unsupported/blocked" in Diagnostics).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] && . .venv/bin/activate
make native
(cd backend && python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &
API=$!; trap 'kill $API' EXIT
(cd frontend && npm run dev)
