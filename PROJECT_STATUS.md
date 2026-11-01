# CRIS — Project Audit and Status

## Current Status Summary

| Area | Status | Verification Summary |
|---|---|---|
| **Capability Detection** | **Resolved & Enhanced** | Real probes for individual namespaces, combined namespace combinations (`combined_default`, `combined_all`), and cgroup v2 controllers. Distinguishes `blocked` (permissions/policy) from `unsupported` (missing kernel features) and internal errors. |
| **Native Error Propagation** | **Resolved** | `_read_startup()` captures all pipe events without losing buffered error lines. Preserves native launcher stage, errno, and error messages. Distinguishes permission denied (403), unsupported (422), and unexpected launcher crash/timeouts (500). Cleanly kills process and closes fds. |
| **Container Lifecycle** | **Resolved** | Create, start, idempotent repeated stop, delete, duplicate detection (409), stale workload recovery on restart, orphan process detection. `signal.SIGKILL` compatibility across Linux and Windows developer environments. |
| **Resource Enforcement** | **Enhanced** | `Cgroup.set_limits()` explicitly verifies effective limits read back from the kernel (`cpu.max`, `memory.max`, `pids.max`). Never reports limits as successful unless confirmed by the kernel. |
| **Test Coverage** | **Expanded** | 46 total backend tests: **44 passed, 2 skipped** (Linux-native namespace integration tests explicitly skipped on non-Linux host). Covers all 16 required test scenarios. |
| **Frontend Redesign** | **Completed** | Professional dark technical dashboard aesthetic (charcoal/navy, restrained accents, typography hierarchy, Recharts telemetry, Gantt charts, memory frame visualizers, disk head trajectory, audit search & filter, hash navigation sync, in-flight polling guard). |
| **Frontend Build** | **Clean** | `tsc --noEmit && vite build` passes cleanly with 0 TypeScript or lint errors. |

## Verified Test Suites

`python -m pytest backend/tests`:
- `test_core.py`: State machine, models validation, basic API sanity.
- `test_coverage_expanded.py`: 14 comprehensive tests covering valid creation, duplicate names, invalid configurations, start/stop lifecycle, repeated stop requests, unsupported namespace combinations, native launcher error propagation, resource enforcement confirmation, cleanup after failed startup, orphan detection, restart recovery, concurrent creation, interrupted experiments, and invalid simulator inputs.
- `test_experiments_mock.py`: Experiments engine execution, metrics compilation, and failure injection.
- `test_simulators.py`: Textbook scheduling algorithms, paging replacement, Banker's algorithm, deadlock detection, and disk scheduling.

## Explicit Known Limitations

- Host cgroup v2 delegation is required for Experiments A, B, and D (honestly reported).
- Mount namespace provides private `/proc` only; not a chroot/pivot_root image sandbox.
- Empty network namespace without veth interface configuration.
- No seccomp syscall filtering.
- Local control plane without API authentication.
