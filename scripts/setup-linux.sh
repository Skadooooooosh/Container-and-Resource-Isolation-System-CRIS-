#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v gcc >/dev/null || { echo "install build tools: sudo apt install build-essential"; exit 1; }
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt
make native test-native
command -v npm >/dev/null && (cd frontend && npm install) || echo "npm not found: skip frontend (install Node 20+)"
echo "Done. Next: ./scripts/run-with-delegation.sh   (gives rootless cgroup v2 limits via systemd)"
