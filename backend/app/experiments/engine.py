"""Reproducible experiments. Each run creates a fresh container, runs a real workload, records real
measurements, destroys the container. Nothing is precomputed; results are only what the kernel reported."""
import json
import statistics
import threading
import time
import uuid
from typing import Optional

from app.containers.manager import ContainerManager
from app.core.errors import CrisError, NotFound, Unsupported
from app.core.models import ContainerCreate, Limits, Namespaces, WorkloadSpec
from app.database.db import Database
from app.isolation import capabilities

EXPERIMENTS = {
    "cpu-comparison": {
        "title": "A: Unconstrained vs CPU-quota-constrained workload",
        "hypothesis": "A fixed CPU job takes about (100 / quota%) times longer under a cpu.max quota, and the cgroup reports throttling.",
        "objective": "Measure wall time, CPU time and throttling for the same bounded job under different cpu.max quotas.",
        "requires": ["cgroup.cpu"], "default_runs": 3,
        "workload": {"type": "cpu", "iterations": 300_000_000, "seconds": 60},
        "configs": [{"label": "unconstrained", "limits": {}},
                    {"label": "50% of one CPU", "limits": {"cpu_quota_percent": 50}},
                    {"label": "25% of one CPU", "limits": {"cpu_quota_percent": 25}}],
        "limitations": "Needs >=1 free host core; noisy neighbours add variance; quota limits bandwidth per 100ms period, it does not pin a core.",
    },
    "memory-limit": {
        "title": "B: Memory-constrained workload",
        "hypothesis": "A 64 MiB allocation succeeds under a 128 MiB memory.max and is OOM-killed under 32 MiB, recorded in memory.events.",
        "objective": "Observe memory.peak, memory.events oom_kill and termination reason under bounded limits.",
        "requires": ["cgroup.memory"], "default_runs": 2,
        "workload": {"type": "memory", "memory_mb": 64, "seconds": 5},
        "configs": [{"label": "128 MiB limit", "limits": {"memory_mb": 128}},
                    {"label": "32 MiB limit", "limits": {"memory_mb": 32}}],
        "limitations": "Swap is set to 0 for the cgroup; behaviour on hosts with memory.oom.group unsupported may differ.",
    },
    "pids-limit": {
        "title": "D: Process-count enforcement (pids.max)",
        "hypothesis": "With pids.max=8, a workload asking for 16 children can fork fewer than 16 and receives EAGAIN.",
        "objective": "Show kernel enforcement of pids.max with a bounded (<=64) fork workload.",
        "requires": ["cgroup.pids"], "default_runs": 2,
        "workload": {"type": "process", "procs": 16, "seconds": 3},
        "configs": [{"label": "no pids limit", "limits": {}}, {"label": "pids.max=8", "limits": {"pids_max": 8}}],
        "limitations": "Count includes the namespace init and the workload itself.",
    },
    "pid-isolation": {
        "title": "C: Process isolation (PID/UTS/mount namespaces)",
        "hypothesis": "Inside a PID namespace the workload sees a tiny PID space and a different namespace inode and hostname.",
        "objective": "Compare namespace inode ids, PID, hostname and number of visible /proc entries inside vs outside.",
        "requires": ["ns.pid"], "default_runs": 1,
        "workload": {"type": "nsinfo", "seconds": 1},
        "configs": [{"label": "no namespaces", "limits": {}, "ns": {"pid": False, "mnt": False, "uts": False, "ipc": False, "net": False, "user": False}},
                    {"label": "pid+mnt+uts+ipc+net", "limits": {}, "ns": {"pid": True, "mnt": True, "uts": True, "ipc": True, "net": True}}],
        "limitations": "Mount namespace here only gives a private /proc mount; it is not a chroot/filesystem sandbox.",
    },
    "competing-workloads": {
        "title": "E: Resource Contention (Competing Workloads)",
        "hypothesis": "Two identical CPU-bound jobs sharing a core will each take ~2x longer than a single isolated run.",
        "objective": "Measure the performance degradation when multiple containers compete for the same physical resources.",
        "requires": ["cgroup.cpu"], "default_runs": 3,
        "workload": {"type": "cpu", "iterations": 100_000_000, "seconds": 30},
        "configs": [{"label": "isolated", "limits": {}}, {"label": "contended", "limits": {}}],
        "limitations": "Requires parallel execution; results depend on host scheduler behavior.",
    },
    "lifecycle-overhead": {
        "title": "F: Lifecycle Overhead",
        "hypothesis": "Container setup (cgroup/ns) adds a constant overhead regardless of workload size.",
        "objective": "Isolate the time cost of CRIS container orchestration vs actual workload execution.",
        "requires": [], "default_runs": 5,
        "workload": {"type": "idle", "seconds": 1},
        "configs": [{"label": "minimal", "limits": {}}],
        "limitations": "Measured as total request time minus workload reported duration.",
    },
    "monitoring-cost": {
        "title": "G: Monitoring Overhead",
        "hypothesis": "High-frequency polling of cgroup stats introduces measurable CPU overhead to the workload.",
        "objective": "Quantify the 'observer effect' of resource monitoring.",
        "requires": ["cgroup.cpu"], "default_runs": 3,
        "workload": {"type": "cpu", "iterations": 200_000_000, "seconds": 30},
        "configs": [{"label": "no-monitoring", "limits": {}}, {"label": "high-freq-monitoring", "limits": {}}],
        "limitations": "Requires a background polling thread during execution.",
    },
}


def _last_json(text: str) -> dict:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except ValueError:
                continue
    return {}


def _summ(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    if not vals:
        return None
    return {"n": len(vals), "mean": round(statistics.mean(vals), 4), "stdev": round(statistics.stdev(vals), 4) if len(vals) > 1 else 0.0,
            "min": min(vals), "max": max(vals)}


class ExperimentEngine:
    def __init__(self, db: Database, mgr: ContainerManager):
        self.db, self.mgr = db, mgr

    def definitions(self):
        return [{"key": k, **{a: v for a, v in d.items() if a != "workload"}, "workload": d["workload"]} for k, d in EXPERIMENTS.items()]

    def start(self, key: str, runs: int | None = None) -> str:
        if key not in EXPERIMENTS:
            raise NotFound(f"unknown experiment '{key}'")
        d = EXPERIMENTS[key]
        missing = [r for r in d["requires"] if capabilities.status_of(r) != "active"]
        if missing:
            raise Unsupported(f"experiment '{key}' cannot run on this host; capabilities not active: {missing}. "
                              "See System Diagnostics. No simulated substitute is produced.", missing=missing)
        runs = runs or d["default_runs"]
        eid = "x-" + uuid.uuid4().hex[:8]
        self.db.execute("INSERT INTO experiments(id,key,status,started_at,progress,definition_json,environment_json) VALUES(?,?,?,?,?,?,?)",
                        (eid, key, "running", time.time(), "0", json.dumps({**d, "runs": runs}), json.dumps(capabilities.detect()["environment"])))
        threading.Thread(target=self._run, args=(eid, key, runs), daemon=True).start()
        return eid

    def _run(self, eid: str, key: str, runs: int):
        d, raw, total, done = EXPERIMENTS[key], [], 0, 0
        total = runs * len(d["configs"])
        try:
            for cfg in d["configs"]:
                # For competing-workloads, we need to run containers in parallel
                if key == "competing-workloads" and cfg["label"] == "contended":
                    # Run 'runs' iterations of parallel pairs
                    for r in range(runs):
                        # Launch two containers simultaneously
                        c1_name = f"{eid}-{r}-cont-1"
                        c2_name = f"{eid}-{r}-cont-2"

                        c1 = None
                        c2 = None
                        try:
                            c1 = self.mgr.create(ContainerCreate(name=c1_name, limits=Limits(**cfg["limits"]), namespaces=Namespaces()))
                            c2 = self.mgr.create(ContainerCreate(name=c2_name, limits=Limits(**cfg["limits"]), namespaces=Namespaces()))

                            # Synchronization barrier to maximize overlap
                            barrier = threading.Barrier(2)
                            results = {}
                            def launch_and_wait(container, label):
                                try:
                                    # Sync before starting to ensure they hit the scheduler together
                                    barrier.wait(timeout=5)
                                    self.mgr.start(container["id"], WorkloadSpec(**d["workload"]))
                                    self.mgr.wait(container["id"], 200)
                                    results[label] = self.mgr.workloads(container["id"])[0]
                                except Exception as e:
                                    results[label] = {"error": str(e)}

                            t1 = threading.Thread(target=launch_and_wait, args=(c1, "w1"))
                            t2 = threading.Thread(target=launch_and_wait, args=(c2, "w2"))

                            t1.start()
                            t2.start()
                            t1.join()
                            t2.join()

                            w1, w2 = results.get("w1"), results.get("w2")

                            if isinstance(w1, dict) and "error" not in w1 and isinstance(w2, dict) and "error" not in w2:
                                raw.append(self._one_results(c1, w1, cfg, "contended-1", r))
                                raw.append(self._one_results(c2, w2, cfg, "contended-2", r))
                            else:
                                err = w1.get("error") if isinstance(w1, dict) and "error" in w1 else (w2.get("error") if isinstance(w2, dict) and "error" in w2 else "unknown")
                                raw.append({"config": cfg["label"], "run": r, "error": f"Parallel run failed: {err}"})
                        except Exception as e:
                            raw.append({"config": cfg["label"], "run": r, "error": str(e)})
                        finally:
                            cleanup_errors = []
                            if c1:
                                try: self.mgr.remove(c1["id"])
                                except Exception as e: cleanup_errors.append(f"c1: {e}")
                            if c2:
                                try: self.mgr.remove(c2["id"])
                                except Exception as e: cleanup_errors.append(f"c2: {e}")
                            if cleanup_errors:
                                raw.append({"config": cfg["label"], "run": r, "cleanup_error": "; ".join(cleanup_errors)})

                        done += 2
                        self.db.execute("UPDATE experiments SET progress=? WHERE id=?", (f"{done}/{total}", eid))
                    continue

                # For monitoring-cost, we need to poll in background
                if key == "monitoring-cost" and cfg["label"] == "high-freq-monitoring":
                    for r in range(runs):
                        c = None
                        try:
                            c = self.mgr.create(ContainerCreate(name=f"{eid}-{r}-mon", limits=Limits(**cfg["limits"]), namespaces=Namespaces()))
                            stop_event = threading.Event()
                            stats_count = [0]
                            errors = []

                            def poll():
                                from app.resources import cgroups
                                try:
                                    cg = cgroups.Cgroup(c.get("path")) if c.get("path") else None
                                    while not stop_event.is_set():
                                        if cg:
                                            cg.stats()
                                            stats_count[0] += 1
                                        time.sleep(0.01)
                                except Exception as e:
                                    errors.append(str(e))

                            mon_thread = threading.Thread(target=poll, daemon=True)
                            mon_thread.start()

                            try:
                                self.mgr.start(c["id"], WorkloadSpec(**d["workload"]))
                                self.mgr.wait(c["id"], 200)
                                w = self.mgr.workloads(c["id"])[0]
                                # Attach monitoring metadata to result
                                w_with_mon = w.copy()
                                w_with_mon["mon_samples"] = stats_count[0]
                                w_with_mon["mon_errors"] = errors
                                raw.append(self._one_results(c, w_with_mon, cfg, f"mon-{r}", r))
                            finally:
                                stop_event.set()
                                mon_thread.join(timeout=1)
                        except Exception as e:
                            raw.append({"config": cfg["label"], "run": r, "error": str(e)})
                        finally:
                            if c:
                                try: self.mgr.remove(c["id"])
                                except Exception as e: raw.append({"config": cfg["label"], "run": r, "cleanup_error": str(e)})

                        done += 1
                        self.db.execute("UPDATE experiments SET progress=? WHERE id=?", (f"{done}/{total}", eid))
                    continue

                for r in range(runs):
                    res, clean_err = self._one(eid, cfg, d["workload"], r)
                    if res:
                        raw.append(res)
                    if clean_err:
                        raw.append({"config": cfg["label"], "run": r, "cleanup_error": clean_err})
                    done += 1
                    self.db.execute("UPDATE experiments SET progress=? WHERE id=?", (f"{done}/{total}", eid))
            self.db.execute("UPDATE experiments SET status='completed',ended_at=?,results_json=? WHERE id=?",
                            (time.time(), json.dumps(self._analyse(key, raw)), eid))
        except Exception as e:  # noqa: BLE001
            self.db.execute("UPDATE experiments SET status='failed',ended_at=?,results_json=? WHERE id=?",
                            (time.time(), json.dumps({"error": str(e), "raw": raw}), eid))
        self.db.event("experiment", "done", None, id=eid, key=key)

    def _one_results(self, c, w, cfg, label, run_idx) -> dict:
        out = _last_json(w.get("output_tail") or "")
        return {"config": cfg["label"], "run": run_idx, "label": label,
                "duration_s": w["duration_s"], "exit_code": w["exit_code"],
                "termination_reason": w["termination_reason"], "cpu_usec": w["cpu_usec"],
                "nr_throttled": w["nr_throttled"], "throttled_usec": w["throttled_usec"],
                "peak_memory_bytes": w["peak_memory_bytes"], "oom_kills": w["oom_kills"],
                "workload_output": out, "effective_limits": c.get("effective_limits")}

    def _one(self, eid, cfg, wl, run_idx) -> tuple[Optional[dict], Optional[str]]:
        ns = Namespaces(**cfg["ns"]) if "ns" in cfg else Namespaces()
        c = self.mgr.create(ContainerCreate(name=f"{eid}-{run_idx}-{abs(hash(cfg['label'])) % 1000}", limits=Limits(**cfg["limits"]), namespaces=ns))
        res = None
        cleanup_err = None
        try:
            self.mgr.start(c["id"], WorkloadSpec(**wl))
            self.mgr.wait(c["id"], 200)
            w = self.mgr.workloads(c["id"])[0]
            out = _last_json(w.get("output_tail") or "")
            host = {}
            if wl["type"] == "nsinfo":
                import os, socket
                try:
                    host = {"host_pid": os.getpid(), "host_hostname": socket.gethostname(),
                            "host_ns": {n: os.readlink(f"/proc/self/ns/{n}") if os.path.exists(f"/proc/self/ns/{n}") else None for n in ("pid", "mnt", "uts", "ipc", "net", "user")},
                            "host_visible_pids": len([x for x in os.listdir("/proc") if x.isdigit()]) if os.path.exists("/proc") else 0}
                except (OSError, AttributeError):
                    host = {"error": "could not collect host namespace info"}
            res = {"config": cfg["label"], "run": run_idx, "duration_s": w["duration_s"], "exit_code": w["exit_code"],
                    "termination_reason": w["termination_reason"], "cpu_usec": w["cpu_usec"], "nr_throttled": w["nr_throttled"],
                    "throttled_usec": w["throttled_usec"], "peak_memory_bytes": w["peak_memory_bytes"], "oom_kills": w["oom_kills"],
                    "workload_output": out, "host_view": host,
                    "effective_limits": c.get("effective_limits")}
        except Exception as e:
            res = {"config": cfg["label"], "run": run_idx, "error": str(e)}
        finally:
            try:
                self.mgr.remove(c["id"])
            except Exception as e:
                cleanup_err = str(e)
        return res, cleanup_err

    def _analyse(self, key: str, raw: list[dict]) -> dict:
        groups: dict[str, list] = {}
        for r in raw:
            groups.setdefault(r["config"], []).append(r)
        summary = {}
        for label, rs in groups.items():
            wall = [r["workload_output"].get("wall_sec") for r in rs if "workload_output" in r]
            summary[label] = {"runs": len(rs), "wall_sec": _summ(wall), "duration_s": _summ([r.get("duration_s") for r in rs]),
                              "cpu_usec": _summ([r.get("cpu_usec") for r in rs]), "throttled_usec": _summ([r.get("throttled_usec") for r in rs]),
                              "nr_throttled": _summ([r.get("nr_throttled") for r in rs]), "peak_memory_bytes": _summ([r.get("peak_memory_bytes") for r in rs]),
                              "oom_kills": _summ([r.get("oom_kills") for r in rs]),
                              "reasons": sorted({r.get("termination_reason", "error") for r in rs}),
                              "forked": _summ([r.get("workload_output", {}).get("forked") for r in rs if "workload_output" in r])}
        notes = []
        labels = list(summary)
        if key == "cpu-comparison" and labels:
            base = (summary[labels[0]]["wall_sec"] or {}).get("mean")
            for l in labels[1:]:
                m = (summary[l]["wall_sec"] or {}).get("mean")
                if base and m:
                    notes.append(f"'{l}' mean wall time was {m / base:.2f}x the unconstrained mean (n={summary[l]['runs']}).")
        if key == "memory-limit" and labels:
            for l in labels:
                notes.append(f"'{l}': termination reasons observed = {summary[l]['reasons']}.")
        if key == "pids-limit" and labels:
            for l in labels:
                f = summary[l]["forked"]
                notes.append(f"'{l}': children successfully forked, mean = {f['mean'] if f else 'n/a'} of 16 requested.")
        if key == "pid-isolation" and labels:
            for r in raw:
                o = r["workload_output"]
                notes.append(f"'{r['config']}': inside PID={o.get('pid')}, hostname={o.get('hostname')}, visible /proc pids={o.get('visible_pids')}, pid-ns={o.get('ns', {}).get('pid')}")
        if key == "competing-workloads" and labels:
            iso = (summary.get("isolated", {}).get("wall_sec") or {}).get("mean")
            con = (summary.get("contended", {}).get("wall_sec") or {}).get("mean")
            if iso and con:
                notes.append(f"Contended run mean wall time was {con / iso:.2f}x the isolated mean (n={summary['contended']['runs']}).")
        if key == "lifecycle-overhead" and labels:
            for l in labels:
                wall = (summary[l]["wall_sec"] or {}).get("mean")
                dur = (summary[l]["duration_s"] or {}).get("mean")
                if wall and dur:
                    notes.append(f"'{l}' estimated setup overhead: {round(wall - dur, 4)}s (mean of {summary[l]['runs']} runs). Note: This is an estimate based on total wall time minus reported workload duration.")
        if key == "monitoring-cost" and labels:
            no_mon = (summary.get("no-monitoring", {}).get("wall_sec") or {}).get("mean")
            hi_mon = (summary.get("high-freq-monitoring", {}).get("wall_sec") or {}).get("mean")
            if no_mon and hi_mon:
                notes.append(f"High-frequency monitoring increased wall time by {round((hi_mon / no_mon - 1) * 100, 2)}% (n={summary['high-freq-monitoring']['runs']}).")
        return {"summary": summary, "raw": raw, "interpretation": notes,
                "note": "Interpretation sentences are generated from the measured values only; compare against the hypothesis yourself."}

    def get(self, eid: str) -> dict:
        r = self.db.one("SELECT * FROM experiments WHERE id=?", (eid,))
        if not r:
            raise NotFound(f"experiment {eid} not found")
        for k in ("definition_json", "environment_json", "results_json"):
            r[k[:-5]] = json.loads(r.pop(k)) if r.get(k) else None
        return r

    def list(self):
        return self.db.query("SELECT id,key,status,started_at,ended_at,progress FROM experiments ORDER BY started_at DESC LIMIT 50")
