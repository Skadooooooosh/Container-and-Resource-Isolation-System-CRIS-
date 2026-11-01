"""cgroup v2 management. All limits are real kernel interface writes, read back for 'effective' values."""
import os
import threading
from pathlib import Path
from typing import Optional

from app.core.config import CGROUP_ROOT, CPU_PERIOD_US
from app.core.errors import Unsupported
from app.core.models import Limits

WANTED = ("cpu", "memory", "pids")
_prep_lock = threading.Lock()
_prep_state: dict = {}


def v2_mounted() -> bool:
    return (CGROUP_ROOT / "cgroup.controllers").exists()


def own_cgroup() -> Optional[Path]:
    try:
        for line in Path("/proc/self/cgroup").read_text().splitlines():
            if line.startswith("0::"):
                return CGROUP_ROOT / line[3:].lstrip("/")
    except OSError:
        pass
    return None


def resolve_base() -> tuple[Optional[Path], str]:
    """Return (base_dir, reason). base_dir is None if we cannot manage cgroups."""
    if not v2_mounted():
        return None, "cgroup v2 unified hierarchy is not mounted at /sys/fs/cgroup"
    env = os.environ.get("CRIS_CGROUP_BASE")
    base = Path(env) if env else own_cgroup()
    if base is None or not base.exists():
        return None, "could not determine a cgroup base directory"
    try:
        if not os.access(base, os.W_OK | os.X_OK):
            from app.core.compat import get_euid
            uid = get_euid()
            uid_str = str(uid) if uid is not None else "unknown"
            return None, f"{base} is not writable by uid {uid_str} (no cgroup delegation; see docs/installation.md)"
    except Exception as e:
        return None, f"error checking access to {base}: {str(e)}"
    return base, "ok"


def _read(p: Path) -> Optional[str]:
    try:
        return p.read_text().strip()
    except OSError:
        return None


def _int(p: Path) -> Optional[int]:
    v = _read(p)
    if v is None or v == "max":
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _kv(p: Path) -> dict:
    out = {}
    for line in (_read(p) or "").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("-").isdigit():
            out[parts[0]] = int(parts[1])
    return out


def prepare_base(base: Path) -> str:
    """Satisfy the 'no internal processes' rule: move *this* process into base/_cris_manager, then
    enable cpu/memory/pids for children. Returns a human-readable status."""
    with _prep_lock:
        if base in _prep_state:
            return _prep_state[base]
        msg = "ok"
        try:
            procs = (_read(base / "cgroup.procs") or "").split()
            if procs:
                mgr = base / "_cris_manager"
                mgr.mkdir(exist_ok=True)
                try:
                    (mgr / "cgroup.procs").write_text(str(os.getpid()))
                except OSError as e:
                    msg = f"could not move manager process out of {base}: {e.strerror}"
            avail = (_read(base / "cgroup.controllers") or "").split()
            enable = " ".join(f"+{c}" for c in WANTED if c in avail)
            if enable:
                (base / "cgroup.subtree_control").write_text(enable)
        except OSError as e:
            msg = f"could not enable controllers: {e.strerror}"
        _prep_state[base] = msg
        return msg


class Cgroup:
    def __init__(self, path: Path):
        self.path = Path(path)

    @classmethod
    def create(cls, name: str) -> "Cgroup":
        base, reason = resolve_base()
        if base is None:
            raise Unsupported("cgroup v2 resource control unavailable: " + reason)
        prepare_base(base)
        p = base / f"cris-{name}"
        p.mkdir(exist_ok=False)
        return cls(p)

    def controllers(self) -> list[str]:
        return (_read(self.path / "cgroup.controllers") or "").split()

    def set_limits(self, lim: Limits) -> dict:
        """Write requested limits; raise Unsupported if the kernel/controller rejects them. Returns effective values."""
        ctl = self.controllers()
        try:
            if lim.cpu_quota_percent is not None:
                self._need("cpu", ctl)
                quota = int(lim.cpu_quota_percent / 100 * CPU_PERIOD_US)
                (self.path / "cpu.max").write_text(f"{quota} {CPU_PERIOD_US}")
            if lim.memory_mb is not None:
                self._need("memory", ctl)
                (self.path / "memory.max").write_text(str(lim.memory_mb * 1024 * 1024))
                for f, v in (("memory.swap.max", "0"), ("memory.oom.group", "1")):
                    try:
                        (self.path / f).write_text(v)
                    except OSError:
                        pass
            if lim.pids_max is not None:
                self._need("pids", ctl)
                (self.path / "pids.max").write_text(str(lim.pids_max))
        except OSError as e:
            raise Unsupported(f"kernel rejected cgroup limit: {e.strerror}", errno=e.errno)
        return self.effective()

    @staticmethod
    def _need(c: str, have: list[str]) -> None:
        if c not in have:
            raise Unsupported(f"cgroup controller '{c}' is not enabled for this cgroup (available: {have})")

    def effective(self) -> dict:
        cm = (_read(self.path / "cpu.max") or "").split()
        cpu_pct = None
        if len(cm) == 2 and cm[0] != "max":
            cpu_pct = round(int(cm[0]) / int(cm[1]) * 100, 2)
        mem = _int(self.path / "memory.max")
        return {"cpu_max_raw": " ".join(cm) or None, "cpu_quota_percent": cpu_pct,
                "memory_max_bytes": mem, "memory_mb": None if mem is None else mem // (1024 * 1024),
                "pids_max": _int(self.path / "pids.max"), "controllers": self.controllers()}

    def stats(self) -> dict:
        cpu = _kv(self.path / "cpu.stat")
        ev = _kv(self.path / "memory.events")
        return {"usage_usec": cpu.get("usage_usec"), "nr_throttled": cpu.get("nr_throttled", 0),
                "throttled_usec": cpu.get("throttled_usec", 0), "nr_periods": cpu.get("nr_periods", 0),
                "memory_current": _int(self.path / "memory.current"), "memory_peak": _int(self.path / "memory.peak"),
                "mem_events": ev, "pids_current": _int(self.path / "pids.current"),
                "pressure_cpu": _read(self.path / "cpu.pressure"), "pressure_memory": _read(self.path / "memory.pressure"),
                "io_stat": _read(self.path / "io.stat")}

    def pids(self) -> list[int]:
        return [int(x) for x in (_read(self.path / "cgroup.procs") or "").split()]

    def kill_all(self) -> None:
        k = self.path / "cgroup.kill"
        if k.exists():
            try:
                k.write_text("1")
                return
            except OSError:
                pass
        import signal
        for pid in self.pids():
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    def remove(self) -> bool:
        try:
            self.path.rmdir()
            return True
        except FileNotFoundError:
            return True
        except OSError:
            return False
