# Testing
`make test` runs: C validation tests (ASan/UBSan), pytest. Integration tests need `make native` and are skipped otherwise.
Cgroup-dependent tests are **not yet written** (they need a delegated cgroup v2 host); manual acceptance steps:
| Test | Action | Expected |
|---|---|---|
| CPU quota | `oslab create-container --name a --cpu 25`; `oslab run <id> --workload cpu` | `nr_throttled > 0`, wall ≈ 4× unconstrained, `effective_limits.cpu_quota_percent = 25` |
| Memory | `--memory 32`, `run --workload memory --mb 64` | `termination_reason=oom_killed`, `oom_kills ≥ 1` |
| pids | create with `pids_max 8` (API), `run --workload process --procs 16` | `forked < 16`, `fork_error` = Resource temporarily unavailable |
| Cleanup | start idle, `stop` | `ps` empty, state STOPPED |
Record the actual outcomes yourself; do not copy these expectations into a report as results.
