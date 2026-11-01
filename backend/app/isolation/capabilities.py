"""Capability detection. Every status comes from a real probe, never a constant."""
import errno
import json
import os
import platform
import subprocess
import time
from pathlib import Path

from app.core.config import CGROUP_ROOT, CRIS_RUN, CRIS_WORKLOAD
from app.core.compat import get_euid
from app.resources import cgroups

_cache: dict = {"t": 0.0, "v": None}


def _f(id_, name, status, detail=""):
    return {"id": id_, "name": name, "status": status, "detail": detail}


def _errno_status(e: int) -> tuple[str, str]:
    if e in (errno.EPERM, errno.EACCES):
        return "blocked", f"{errno.errorcode.get(e)}: permission denied by kernel policy/LSM/sysctl"
    if e in (errno.EINVAL, errno.ENOSYS, errno.ENOSPC):
        return "unsupported", f"{errno.errorcode.get(e)}: not supported or limit reached"
    return "failed", f"{errno.errorcode.get(e, e)}: {os.strerror(e)}"


def detect(force: bool = False) -> dict:
    if not force and _cache["v"] and time.time() - _cache["t"] < 30:
        return _cache["v"]
    u = platform.uname()
    wsl = "microsoft" in u.release.lower()
    env = {"kernel": u.release, "arch": u.machine, "system": u.system, "wsl": wsl, "euid": get_euid(),
           "python": platform.python_version(), "cpus": os.cpu_count()}
    feats = []
    if u.system != "Linux":
        feats.append(_f("platform", "Linux kernel", "unsupported", "CRIS requires Linux (use WSL2 or a VM)"))
        res = {"environment": env, "features": feats, "generated_at": time.time()}
        _cache.update(t=time.time(), v=res)
        return res
    feats.append(_f("platform", "Linux kernel", "active", u.release + (" (WSL2: check cgroup/ns limits)" if wsl else "")))
    feats.append(_f("procfs", "procfs", "active" if Path("/proc/self/stat").exists() else "unsupported"))
    built = CRIS_RUN.exists() and CRIS_WORKLOAD.exists()
    feats.append(_f("native", "Native binaries (cris_run, cris_workload)",
                    "active" if built else "supported_not_configured", "" if built else "run `make native`"))
    probe = None
    if built:
        try:
            probe = json.loads(subprocess.run([str(CRIS_RUN), "--probe"], capture_output=True, text=True, timeout=10).stdout)
        except Exception as ex:  # noqa: BLE001
            feats.append(_f("ns.probe", "Namespace probe", "failed", str(ex)))
    for ns in ("user", "pid", "mnt", "uts", "ipc", "net"):
        if probe is None:
            feats.append(_f(f"ns.{ns}", f"{ns.upper()} namespace", "unknown", "native probe unavailable"))
        elif probe[ns] == 0:
            feats.append(_f(f"ns.{ns}", f"{ns.upper()} namespace", "active", "clone(2) succeeded"))
        else:
            s, d = _errno_status(probe[ns])
            feats.append(_f(f"ns.{ns}", f"{ns.upper()} namespace", s, d))
    if not cgroups.v2_mounted():
        feats.append(_f("cgroup.v2", "cgroup v2", "unsupported", "no unified hierarchy at /sys/fs/cgroup"))
        for c in ("cpu", "memory", "pids", "io"):
            feats.append(_f(f"cgroup.{c}", f"cgroup {c} controller", "unsupported", "cgroup v2 not mounted"))
    else:
        feats.append(_f("cgroup.v2", "cgroup v2", "active"))
        root_ctl = (CGROUP_ROOT / "cgroup.controllers").read_text().split()
        base, reason = cgroups.resolve_base()
        if base is None:
            feats.append(_f("cgroup.delegation", "cgroup delegation", "blocked", reason))
            for c in ("cpu", "memory", "pids", "io"):
                feats.append(_f(f"cgroup.{c}", f"cgroup {c} controller",
                                "blocked" if c in root_ctl else "unsupported",
                                "present on host but not usable without delegation" if c in root_ctl else "controller absent"))
        else:
            note = cgroups.prepare_base(base)
            feats.append(_f("cgroup.delegation", "cgroup delegation", "active" if note == "ok" else "failed", f"{base}: {note}"))
            avail = (base / "cgroup.subtree_control").read_text().split() if (base / "cgroup.subtree_control").exists() else []
            for c in ("cpu", "memory", "pids", "io"):
                if c in avail:
                    feats.append(_f(f"cgroup.{c}", f"cgroup {c} controller", "active", "enabled in subtree_control"))
                elif c in root_ctl:
                    feats.append(_f(f"cgroup.{c}", f"cgroup {c} controller", "supported_not_configured",
                                    "present but not enabled for our subtree" + (" (io needs a block device policy)" if c == "io" else "")))
                else:
                    feats.append(_f(f"cgroup.{c}", f"cgroup {c} controller", "unsupported", "controller absent from kernel/cgroup root"))
    res = {"environment": env, "features": feats, "generated_at": time.time()}
    _cache.update(t=time.time(), v=res)
    return res


def status_of(feature_id: str) -> str:
    for f in detect()["features"]:
        if f["id"] == feature_id:
            return f["status"]
    return "unknown"
