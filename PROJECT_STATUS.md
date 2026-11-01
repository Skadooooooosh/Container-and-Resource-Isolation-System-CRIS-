# PROJECT_STATUS

## Verified in the build sandbox (Linux 6.18, x86_64, uid 0, Python 3.12, Node 22) — actually executed
- `make -C native all test`: compiles with `-Wall -Wextra -Wpedantic -Wshadow`, no warnings; ASan/UBSan validation test passes.
- `cris_run --probe` and real namespace launch (pid,mnt,uts,ipc,net): workload saw PID 2/PPID 1 (init=PID 1), 2 visible /proc entries, hostname = container name, distinct namespace inodes.
- `pytest`: **27 passed** (simulators against textbook values; state machine; validation; API; real namespace isolation; stop kills workload; duplicate start → 409).
- CLI: `oslab doctor`, `experiment run pid-isolation` (real run, real measurements), and honest refusal of cgroup-dependent experiments.
- Frontend: `tsc --noEmit` clean, `vite build` succeeds.

## Verified in the uploaded project review environment
- `cd backend && python -m pytest -q`: **30 passed, 2 skipped** after fixing a missing `Optional` import in `app/experiments/engine.py` and correcting the experiment-E failure-injection mock.

## Verified on Windows (Developer Host)
- **Backend Stability**: `pytest` executes without `AttributeError`. Portable unit tests (simulators, state machine, validation, API basics) pass.
- **Graceful Degradation**: 
    - `os.sysconf`, `os.geteuid`, and `os.getloadavg` are safely wrapped; no crashes.
    - `/api/system/capabilities` correctly reports Linux features as `unsupported` on Windows.
    - `ExperimentEngine` correctly refuses to run Experiments A-D on Windows with a structured `Unsupported` error.
- **Testing Baseline**: Linux-native integration tests are explicitly skipped via `@pytest.mark.skipif`.
- **Frontend**: `npm run build` succeeds (tsc clean, vite build OK).
- **Mock test correction**: `test_experiment_e_one_fails` now injects a failure on the third start call (the second contended workload) instead of checking a container ID that the mock never returns.

## NOT verified (sandbox had no cgroup v2 mount) — code written, never executed against a real kernel
- cgroup creation, `cpu.max` / `memory.max` / `pids.max` writes, effective read-back, `cgroup.kill`, throttling / memory.events / OOM accounting.
- Experiments A (cpu-comparison), B (memory-limit), D (pids-limit). Run them on a cgroup-v2 host and fix any issue first.
- Unprivileged (non-root) user-namespace path: written (uid/gid maps) but only exercised as root.
- Frontend never rendered in a browser; no React component tests.

## Implemented (Pending Linux Validation)
- Experiments E (competing workloads), F (lifecycle report), G (monitoring overhead). Logic implemented with parallel threading for contention, background polling for monitoring, and recorded cleanup error tracking.

## Not implemented
- io.max; SSE/WebSocket live stream (UI polls);
- veth networking; pivot_root filesystem sandbox; filesystem & protection labs; MLFQ aging; Mermaid diagrams beyond `docs/architecture.md`;
- frontend tests; docker-compose; API reference doc (use `/docs` OpenAPI).

## Next concrete steps
1. On Ubuntu with systemd: `./scripts/run-with-delegation.sh`, then `oslab doctor` — cgroup rows must be `active`.
2. `oslab experiment run cpu-comparison` / `memory-limit` / `pids-limit`; fix whatever fails.
3. Validate Experiments E-G on a cgroup-v2 host.
4. Add pivot_root rootfs, frontend tests, SSE stream.
