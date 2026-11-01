# Installation
Ubuntu 22.04+/24.04 (bare metal, VM, or WSL2 with systemd enabled). Needs `build-essential python3-venv nodejs(20+)`.
1. `./scripts/setup-linux.sh`
2. Check cgroup v2: `stat -fc %T /sys/fs/cgroup` → `cgroup2fs`.
3. Rootless delegation (one time, root): create `/etc/systemd/system/user@.service.d/delegate.conf` with `[Service]\nDelegate=cpu cpuset io memory pids`, `systemctl daemon-reload`, re-login.
4. `./scripts/run-with-delegation.sh`; open System Diagnostics — cgroup rows should read `active`.
Why the manager moves itself into `_cris_manager`: cgroup v2's "no internal processes" rule forbids enabling controllers on a cgroup that contains processes.
WSL2: enable systemd (`/etc/wsl.conf` `[boot] systemd=true`); cgroup v2 is the default on recent WSL kernels; some controllers may be absent — Diagnostics will say so.
Without delegation you still get namespaces, monitoring (via /proc) and the OS lab.
