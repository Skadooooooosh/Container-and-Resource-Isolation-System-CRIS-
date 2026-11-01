#!/usr/bin/env bash
# Runs the API inside a systemd user scope with cgroup delegation so CPU/memory/pids limits work WITHOUT root.
# Requires: systemd user session, cgroup v2, and cpu/memory/pids delegated to user services
# (one-time, as root:  mkdir -p /etc/systemd/system/user@.service.d &&
#   printf '[Service]\nDelegate=cpu cpuset io memory pids\n' > /etc/systemd/system/user@.service.d/delegate.conf && systemctl daemon-reload)
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] && . .venv/bin/activate
make native
exec systemd-run --user --scope -p Delegate=yes -- bash -c 'cd backend && python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000'
