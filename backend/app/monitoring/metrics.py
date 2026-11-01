"""Real measurements from /proc on Linux or kernel32 on Windows. Nothing here is estimated or simulated."""
import os
import sys
import time
from pathlib import Path
from typing import Optional
from app.core.compat import sysconf, get_loadavg

CLK = sysconf("SC_CLK_TCK") or 100
PAGE = sysconf("SC_PAGE_SIZE") or 4096


def proc_info(pid: int) -> Optional[dict]:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        status = Path(f"/proc/{pid}/status").read_text()
    except OSError:
        return None
    comm = stat[stat.index("(") + 1: stat.rindex(")")]
    f = stat[stat.rindex(")") + 2:].split()
    nspid, rss_kb = [pid], None
    for line in status.splitlines():
        if line.startswith("NSpid:"):
            nspid = [int(x) for x in line.split()[1:]]
        elif line.startswith("VmRSS:"):
            rss_kb = int(line.split()[1])
    try:
        boot = float(Path("/proc/uptime").read_text().split()[0])
    except OSError:
        boot = 0.0
    start = int(f[19])
    return {"pid": pid, "ppid": int(f[1]), "name": comm, "state": f[0],
            "cpu_ticks": int(f[11]) + int(f[12]), "starttime": start,
            "elapsed_s": round(max(0.0, boot - start / CLK), 2),
            "rss_kb": rss_kb, "ns_pids": nspid,
            "container_pid": nspid[-1], "host_pid": nspid[0]}


def starttime_of(pid: int) -> Optional[int]:
    info = proc_info(pid)
    return info["starttime"] if info else None


def descendants(root: int) -> list[int]:
    """root plus all live descendants, via PPid scan of /proc."""
    if not Path("/proc").exists():
        return [root] if proc_info(root) else []
    children: dict[int, list[int]] = {}
    try:
        for d in os.listdir("/proc"):
            if d.isdigit():
                i = proc_info(int(d))
                if i:
                    children.setdefault(i["ppid"], []).append(i["pid"])
    except OSError:
        return [root] if proc_info(root) else []
    out, stack = [], [root]
    while stack:
        p = stack.pop()
        if proc_info(p):
            out.append(p)
        stack.extend(children.get(p, []))
    return out


def tree_usage(root: int) -> dict:
    ticks = rss = n = 0
    for p in descendants(root):
        i = proc_info(p)
        if i:
            ticks += i["cpu_ticks"]
            rss += (i["rss_kb"] or 0) * 1024
            n += 1
    return {"cpu_usec": int(ticks / CLK * 1e6), "rss_bytes": rss, "pids": n}


_last_cpu: dict = {}


def _linux_host_metrics() -> dict:
    def cpu_times():
        v = [int(x) for x in Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
        return sum(v), v[3] + (v[4] if len(v) > 4 else 0)

    t1, i1 = cpu_times()
    prev = _last_cpu.get("linux")
    if prev is None or t1 - prev[0] == 0:
        time.sleep(0.1)
        prev = (t1, i1)
        t1, i1 = cpu_times()
    _last_cpu["linux"] = (t1, i1)
    dt = t1 - prev[0]
    cpu = round(100 * (1 - (i1 - prev[1]) / dt), 1) if dt > 0 else None
    mi = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        k, v = line.split(":")
        mi[k] = int(v.split()[0]) * 1024
    total, avail = mi.get("MemTotal", 0), mi.get("MemAvailable", 0)
    load = get_loadavg()
    return {
        "ts": time.time(),
        "cpu_percent": cpu,
        "cpus": os.cpu_count(),
        "mem_total_bytes": total,
        "mem_used_bytes": total - avail,
        "mem_percent": round(100 * (total - avail) / total, 1) if total else None,
        "loadavg": load,
        "source": "/proc/stat,/proc/meminfo",
    }


def _windows_host_metrics() -> dict:
    import ctypes

    cpu = None
    try:
        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]

        idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
        if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            def ft_to_int(ft):
                return (ft.dwHighDateTime << 32) | ft.dwLowDateTime

            i_val = ft_to_int(idle)
            k_val = ft_to_int(kernel)
            u_val = ft_to_int(user)
            t_val = k_val + u_val  # In Windows GetSystemTimes, kernel time includes idle time
            prev = _last_cpu.get("win")
            if prev is None or t_val - prev[0] == 0:
                time.sleep(0.1)
                prev = (t_val, i_val)
                ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
                i_val = ft_to_int(idle)
                t_val = ft_to_int(kernel) + ft_to_int(user)
            _last_cpu["win"] = (t_val, i_val)
            dt = t_val - prev[0]
            di = i_val - prev[1]
            if dt > 0:
                cpu = round(max(0.0, min(100.0, 100.0 * (1.0 - (di / dt)))), 1)
    except Exception:
        cpu = None

    total, avail = None, None
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            total = int(stat.ullTotalPhys)
            avail = int(stat.ullAvailPhys)
    except Exception:
        total, avail = None, None

    used = (total - avail) if (total is not None and avail is not None) else None
    mem_pct = round(100.0 * used / total, 1) if (total and used is not None) else None

    return {
        "ts": time.time(),
        "cpu_percent": cpu,
        "cpus": os.cpu_count(),
        "mem_total_bytes": total,
        "mem_used_bytes": used,
        "mem_percent": mem_pct,
        "loadavg": None,
        "source": "Windows kernel32 (GetSystemTimes, GlobalMemoryStatusEx)",
    }


def host_metrics() -> dict:
    if Path("/proc/stat").exists() and Path("/proc/meminfo").exists():
        try:
            return _linux_host_metrics()
        except OSError:
            pass
    if sys.platform == "win32":
        return _windows_host_metrics()
    return {
        "ts": time.time(),
        "cpu_percent": None,
        "cpus": os.cpu_count(),
        "mem_total_bytes": None,
        "mem_used_bytes": None,
        "mem_percent": None,
        "loadavg": None,
        "source": "unsupported platform",
    }
