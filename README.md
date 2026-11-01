# CRIS — Container & Resource Isolation System

A Linux OS engineering platform featuring a real container launcher built on **Linux namespaces** and **cgroups v2**, a FastAPI control plane, a redesigned professional React dashboard, a reproducible experiment engine, and an educational OS-syllabus simulator laboratory (explicitly labelled as simulation).

Nothing in the UI is fabricated: unsupported or permission-blocked features honestly report *why* they cannot run.

## Architecture & Layers
`React UI (Vite + TypeScript) → FastAPI + SQLite → cris_run (C, clone / cgroup attach / PID-1 reaper) → Linux kernel`

| Path | Role |
|---|---|
| `native/src/cris_run.c` | Launcher: `clone(2)` namespaces (pid, mnt, uts, ipc, net, user), uid/gid maps, **cgroup attach before exec**, PID-1 reaping, timeout, structured JSON events |
| `native/src/cris_workload.c` | Bounded workloads: cpu, memory, process, mixed, idle, nsinfo (hard caps) |
| `backend/app/resources/cgroups.py` | cgroup v2 controller configuration (`cpu.max`, `memory.max`, `pids.max`), kernel confirmation verification, `cgroup.kill` |
| `backend/app/containers/manager.py` | Lifecycle state machine (CREATED → STARTING → RUNNING → STOPPING → STOPPED / FAILED), PID+starttime liveness verification, idempotent stop, restart recovery |
| `backend/app/isolation/capabilities.py` | Real probes for individual & combined namespaces + cgroup controllers (`active`, `supported_not_configured`, `unsupported`, `blocked`, `failed`) |
| `backend/app/experiments/engine.py` | Experiments A–G with n-run statistical distributions (mean ± stdev), raw JSON exports |
| `backend/app/simulators/` | CPU Scheduling (7 algorithms), Paging / TLB / Replacement, Banker's algorithm, Deadlock detection, Disk arm scheduling, Concurrency synchronization lab |
| `backend/app/cli.py` | `oslab` CLI management tool |
| `frontend/` | Redesigned technical dark infrastructure dashboard (Overview, Containers, Experiment Lab, OS Lab, System Diagnostics, Logs & Events, Docs) |

## Quick Start (Ubuntu / WSL2 / Linux VM)

```bash
# 1. Setup environment and build native binaries & frontend
./scripts/setup-linux.sh          # venv, python dependencies, native compile, frontend npm build

# 2. Check host capabilities
./scripts/oslab doctor            # inspect what THIS kernel and privilege level supports

# 3. Launch control plane and dashboard
./scripts/run-with-delegation.sh  # API on :8000 with rootless cgroup limits (systemd)   -- or --
./scripts/run-development.sh      # API on :8000 + UI on :5173 without cgroup delegation (namespaces only)
```

- **Dashboard UI**: `http://localhost:5173`
- **Interactive OpenAPI Docs**: `http://localhost:8000/docs`
- **CLI Commands**:
  ```bash
  oslab create-container --name demo --cpu 50 --memory 64
  oslab list
  oslab run <id> --workload cpu --seconds 10
  oslab stats <id>
  oslab ps <id>
  oslab stop <id>
  oslab destroy <id>
  oslab experiment run cpu-comparison
  ```

## Testing

```bash
# Run backend pytest suite (unit, API, extended lifecycle, error propagation, simulators)
python -m pytest backend/tests

# Run native launcher unit validation
make -C native test

# Build frontend production bundle
cd frontend && npm run build
```

## Honest Security & System Limitations

CRIS is an educational and systems engineering platform designed to explore kernel isolation primitives. It is **not** a hardened multi-tenant container runtime like Docker or containerd:
1. **Filesystem Isolation**: The mount namespace creates a private `/proc` mount; it is **not** a `pivot_root` or `chroot` filesystem sandbox. Workload processes share the host root filesystem.
2. **Syscall Filtering**: Seccomp filtering is not implemented. Workloads have access to standard permitted syscalls.
3. **Network Isolation**: Network namespaces are initialized empty with the loopback interface down; no virtual ethernet (`veth`) pair or bridge setup is configured.
4. **API Authentication**: The FastAPI control plane and WebSocket/polling endpoints are unauthenticated and intended for local development, VMs, and laboratory use.
5. **cgroup v2 Delegation**: cgroup limits require a Linux kernel with unified cgroup v2 hierarchy and write delegation (via systemd or root). Without delegation, limit requests fail honestly with actionable error messages.
