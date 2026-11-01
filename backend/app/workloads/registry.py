"""Predefined workloads only. Arguments are built as an argv list; no shell is ever involved."""
from app.core.config import CRIS_WORKLOAD
from app.core.models import WorkloadSpec, WorkloadType


def build_argv(spec: WorkloadSpec) -> list[str]:
    w, t = str(CRIS_WORKLOAD), spec.type
    s = ["--seconds", str(spec.seconds)]
    if t == WorkloadType.cpu:
        return [w, "cpu", "--iterations", str(spec.iterations), *s]
    if t == WorkloadType.memory:
        return [w, "memory", "--mb", str(spec.memory_mb), *s]
    if t == WorkloadType.mixed:
        return [w, "mixed", "--mb", str(spec.memory_mb), "--iterations", str(spec.iterations), *s]
    if t == WorkloadType.process:
        return [w, "process", "--procs", str(spec.procs), *s]
    if t == WorkloadType.idle:
        return [w, "idle", *s]
    return [w, "nsinfo"]


DESCRIPTIONS = {
    "cpu": "Fixed amount of integer work; wall time depends on CPU quota",
    "memory": "Allocates and touches N MiB (max 512), then holds briefly",
    "process": "Forks up to N sleeping children (max 64); shows pids.max effect",
    "mixed": "Memory allocation followed by CPU work",
    "idle": "Sleeps; for lifecycle and monitoring demos",
    "nsinfo": "Prints PID, hostname and namespace inode ids as seen from inside",
}
