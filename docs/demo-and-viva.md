# Demo (≈7 min)
1. `oslab doctor` → explain statuses. 2. UI → Diagnostics. 3. Containers → create `demo` (cpu 50, mem 64) → Start `nsinfo`, show logs: PID 2, hostname `demo`, different ns inodes.
4. Start `cpu`; show live chart, throttling. 5. Experiment Lab → run `cpu-comparison`; show table, export JSON. 6. Stop an `idle` container, show `ps` empty. 7. OS Lab: RR vs SRTF Gantt; LRU vs FIFO faults; Banker unsafe request.

# Viva starters
- *Container vs VM?* Shared kernel; isolation by namespaces (what you see) + cgroups (what you use).
- *Why is the workload PID 2 inside?* The launcher is PID 1 (init/reaper) in the new PID ns; it forks the workload.
- *Why attach to the cgroup before exec?* Otherwise the workload could allocate before the limit exists.
- *cpu.max 50000 100000?* 50 ms CPU time per 100 ms period; throttled when exhausted; not core pinning.
- *Why can't enable controllers on a cgroup with processes?* No-internal-process constraint of cgroup v2.
- *Why is a mount namespace not a sandbox?* It only changes the mount table; host paths stay reachable without pivot_root/chroot.
- *Why is Optimal paging not real?* Requires future knowledge; it is a lower bound.
- *Deadlock detection vs avoidance vs prevention?* Detect after the fact; avoid with Banker's safe-state check; prevent by breaking one of the four conditions.
- *Stale PID problem?* PID reuse; we store `/proc` starttime and compare before signalling.
