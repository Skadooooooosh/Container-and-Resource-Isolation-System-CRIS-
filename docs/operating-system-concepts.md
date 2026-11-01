# OS concepts ↔ implementation
| Topic | Status | Where |
|---|---|---|
| Processes, PID 1, reaping, orphan re-parenting | **Real** | `cris_run.c` (init loop), `process` workload |
| System calls (clone, mount, sethostname, prctl, waitpid) | **Real** | `cris_run.c` |
| Namespaces (pid, mnt, uts, ipc, net, user) | **Real** | `cris_run.c`, Experiment C |
| cgroups v2: CPU bandwidth, memory, pids | **Real code** (needs delegated cgroup v2 host) | `cgroups.py` |
| CPU quota ≠ core pinning: `cpu.max "quota period"` limits CPU time per 100 ms period; threads can still run on any core | explained | Experiment A |
| Virtual vs resident vs cgroup-charged memory | explained; RSS and `memory.current` are shown | `metrics.py` |
| CPU scheduling algorithms | **Simulated** | `simulators/scheduling.py` |
| Paging, TLB, replacement, partitions | **Simulated** | `simulators/memory.py` |
| Deadlock: Banker, detection, wait-for cycle | **Simulated** | `simulators/deadlock.py` |
| Synchronization: race, semaphores/mutex producer–consumer (real threads), dining philosophers | simulation / real threads | `simulators/sync.py` |
| Disk scheduling | **Simulated** | `simulators/disk.py` |
| Filesystems, protection labs | **Not implemented** (theory only) | — |
