# CRIS — Container & Resource Isolation System

A Linux OS project: a real container launcher built on **namespaces** and **cgroups v2**, a FastAPI control plane,
a React dashboard, a reproducible experiment engine, and an OS-syllabus simulator lab (clearly labelled as simulation).

**This is a framework / working skeleton.** See `PROJECT_STATUS.md` for exactly what is implemented, what was tested,
and what is not done. Nothing in the UI is fabricated: unsupported features report *why* they are unsupported.

## Layers
`React UI → FastAPI + SQLite → cris_run (C, clone/cgroup attach/PID-1 reaper) → Linux kernel`

| Path | Role |
|---|---|
| `native/src/cris_run.c` | Launcher: `clone(2)` namespaces (pid,mnt,uts,ipc,net,user), uid/gid maps, **cgroup attach before exec**, PID-1 reaping, timeout, JSON events |
| `native/src/cris_workload.c` | Bounded workloads: cpu, memory, process, mixed, idle, nsinfo (hard caps) |
| `backend/app/resources/cgroups.py` | cgroup v2 writes (`cpu.max`, `memory.max`, `pids.max`), read-back of *effective* values, `cgroup.kill` |
| `backend/app/containers/` | State machine + lifecycle (pid + starttime verification, reconcile on restart) |
| `backend/app/isolation/capabilities.py` | Real probes → active / supported_not_configured / unsupported / blocked / failed / unknown |
| `backend/app/experiments/` | Experiments A–D (cpu quota, memory limit, pids limit, PID isolation) with n-run statistics |
| `backend/app/simulators/` | Scheduling (7 algos), paging/TLB/replacement, Banker/deadlock detection, disk scheduling, sync lab |
| `backend/app/cli.py` | `oslab` CLI |
| `frontend/` | Vite + React + TS dashboard (Overview, Containers, Experiment Lab, OS Lab, Diagnostics, Logs, Docs) |

## Quick start (Ubuntu / WSL2 / Linux VM)
```bash
./scripts/setup-linux.sh          # venv, deps, build C, C unit tests, npm install
./scripts/oslab doctor            # what does THIS host support?
./scripts/run-with-delegation.sh  # API on :8000 with rootless cgroup limits (systemd)   -- or --
./scripts/run-development.sh      # API + UI without cgroup delegation (namespaces only)
# UI: http://localhost:5173    API docs: http://localhost:8000/docs
```
CLI: `oslab create-container --name demo --cpu 50 --memory 64 | list | run <id> --workload cpu | stats <id> | ps <id> | stop <id> | destroy <id> | experiment run cpu-comparison`

## Tests
`make test` (C unit tests under ASan/UBSan + pytest: simulators vs textbook examples, state machine, API, and real-namespace integration tests that auto-skip if binaries aren't built).

## Honest limitations
- cgroup limits need cgroup v2 + delegation (see `docs/installation.md`). Without it, limit requests fail with a clear error; experiments A, B, D refuse to run (no fake data).
- The mount namespace only gives a private `/proc`; it is **not** a chroot/pivot_root filesystem sandbox. See `docs/security.md`.
- Network namespace is created empty (loopback down); no veth/bridge setup is attempted.
- Experiments E (competing workloads), F (lifecycle overhead), and G (monitoring overhead) are implemented in the experiment engine but still require validation on a Linux host with cgroup v2 and suitable delegation.
- I/O limits (`io.max`) are **not implemented**.
