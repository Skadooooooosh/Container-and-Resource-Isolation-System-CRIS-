from __future__ import annotations
"""Container lifecycle. The DB is metadata; liveness is always verified against /proc (pid + starttime)."""
import json
import os
import select
import signal
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from subprocess import Popen, STDOUT
from typing import Optional

from app.containers.states import REMOVABLE, State, can_transition
from app.core import config
from app.core.errors import InvalidTransition, LaunchFailed, NotFound, Unsupported
from app.core.models import ContainerCreate, Limits, WorkloadSpec
from app.database.db import Database
from app.isolation import capabilities
from app.monitoring import metrics
from app.resources import cgroups
from app.resources.cgroups import Cgroup
from app.workloads.registry import build_argv


class ContainerManager:
    def __init__(self, db: Database):
        self.db = db
        self._lock = threading.RLock()
        self._threads: dict[str, threading.Thread] = {}
        self._stop_req: set[str] = set()
        self.samples: dict[str, deque] = {}
        self.reconcile()

    # ---------- helpers ----------
    def _row(self, cid: str) -> dict:
        r = self.db.one("SELECT * FROM containers WHERE id=?", (cid,))
        if not r:
            raise NotFound(f"container {cid} not found")
        return r

    def _set_state(self, cid: str, new: State, **cols) -> None:
        with self._lock:
            cur = State(self._row(cid)["state"])
            if cur != new and not can_transition(cur, new):
                raise InvalidTransition(f"{cur.value} -> {new.value} is not allowed", current=cur.value, requested=new.value)
            sets = ",".join(f"{k}=?" for k in ["state", *cols])
            self.db.execute(f"UPDATE containers SET {sets} WHERE id=?", [new.value, *cols.values(), cid])
            self.db.event("state", "ok", cid, **{"from": cur.value, "to": new.value})

    def _pid_alive(self, row: dict) -> bool:
        pid, st = row.get("host_pid"), row.get("pid_starttime")
        return bool(pid) and metrics.starttime_of(pid) == st      # PID reuse safe

    def _cg(self, row: dict) -> Optional[Cgroup]:
        return Cgroup(row["cgroup_path"]) if row.get("cgroup_path") else None

    def view(self, row: dict) -> dict:
        d = dict(row)
        d["limits"] = json.loads(d.pop("limits_json"))
        d["namespaces"] = json.loads(d.pop("ns_json"))
        cg = self._cg(row)
        d["effective_limits"] = cg.effective() if cg and Path(cg.path).exists() else None
        d["pid_verified_alive"] = self._pid_alive(row) if row["state"] in ("RUNNING", "STOPPING", "STARTING") else False
        return d

    # ---------- reconcile after restart ----------
    def reconcile(self) -> None:
        for r in self.db.query("SELECT * FROM containers WHERE state IN ('STARTING','RUNNING','STOPPING')"):
            if r["id"] in self._threads:
                continue
            if self._pid_alive(r):
                self.db.event("reconcile", "orphan_running", r["id"], host_pid=r["host_pid"])
                continue      # still genuinely alive; stop() can kill it (pid+starttime verified)
            self.db.execute("UPDATE containers SET state='FAILED', host_pid=NULL WHERE id=?", (r["id"],))
            self.db.execute("UPDATE workloads SET ended_at=?, termination_reason='lost_on_restart' "
                            "WHERE container_id=? AND ended_at IS NULL", (time.time(), r["id"]))
            self.db.event("reconcile", "marked_failed_stale_process", r["id"])

    # ---------- operations ----------
    def create(self, req: ContainerCreate) -> dict:
        if self.db.one("SELECT 1 x FROM containers WHERE name=?", (req.name,)):
            raise InvalidTransition(f"container name '{req.name}' already exists")
        if req.limits.any() and cgroups.resolve_base()[0] is None:
            raise Unsupported("resource limits requested but cgroup v2 delegation is unavailable: "
                              + cgroups.resolve_base()[1])
        cid = "c-" + uuid.uuid4().hex[:10]
        cg: Optional[Cgroup] = None
        try:
            if cgroups.resolve_base()[0] is not None:
                cg = Cgroup.create(cid)
                if req.limits.any():
                    eff = cg.set_limits(req.limits)
                    self.db.event("limits_applied", "ok", cid, requested=req.limits.model_dump(), effective=eff)
            self.db.execute("INSERT INTO containers(id,name,state,created_at,limits_json,ns_json,cgroup_path) VALUES(?,?,?,?,?,?,?)",
                            (cid, req.name, State.CREATED.value, time.time(), req.limits.model_dump_json(),
                             req.namespaces.model_dump_json(), str(cg.path) if cg else None))
        except Exception as e:
            if cg:
                cg.remove()                           # no leaked cgroup after failed creation
            self.db.event("create", "failed", None, name=req.name, error=str(e))
            raise
        self.db.event("create", "ok", cid, name=req.name)
        return self.view(self._row(cid))

    def list(self) -> list[dict]:
        return [self.view(r) for r in self.db.query("SELECT * FROM containers ORDER BY created_at DESC")]

    def get(self, cid: str) -> dict:
        return self.view(self._row(cid))

    def update_limits(self, cid: str, lim: Limits) -> dict:
        row = self._row(cid)
        if row["state"] in ("STARTING", "RUNNING", "STOPPING"):
            raise InvalidTransition("limits can only be changed while the container is not running")
        cg = self._cg(row)
        if cg is None:
            raise Unsupported("no cgroup for this container (cgroup v2 unavailable)")
        merged = Limits(**{**json.loads(row["limits_json"]), **lim.model_dump(exclude_none=True)})
        eff = cg.set_limits(merged)
        self.db.execute("UPDATE containers SET limits_json=? WHERE id=?", (merged.model_dump_json(), cid))
        self.db.event("limits_applied", "ok", cid, requested=merged.model_dump(), effective=eff)
        return self.get(cid)

    def start(self, cid: str, spec: WorkloadSpec) -> dict:
        with self._lock:
            row = self._row(cid)
            self._set_state(cid, State.STARTING)       # duplicate start -> InvalidTransition (409)
        if not config.CRIS_RUN.exists():
            self._set_state(cid, State.FAILED)
            raise LaunchFailed("native binaries missing: run `make native`")
        ns = json.loads(row["ns_json"])
        nsarg = ",".join(k for k in ("pid", "mnt", "uts", "ipc", "net", "user") if ns.get(k))
        cg = self._cg(row)
        base = cg.stats() if cg else {}
        r_fd, w_fd = os.pipe()
        log = open(config.LOG_DIR / f"{cid}.log", "ab")
        cmd = [str(config.CRIS_RUN), "--ns", nsarg, "--hostname", row["name"], "--timeout", str(min(spec.seconds + 15, 150)),
               "--event-fd", str(w_fd)]
        if cg:
            cmd += ["--cgroup", str(cg.path)]
        cmd += ["--", *build_argv(spec)]
        wid = None
        try:
            proc = Popen(cmd, stdout=log, stderr=STDOUT, pass_fds=(w_fd,),
                         start_new_session=True, env={"PATH": "/usr/bin:/bin"})
        except OSError as e:
            os.close(r_fd); os.close(w_fd); log.close()
            self._set_state(cid, State.FAILED)
            self.db.event("start", "failed", cid, error=str(e))
            raise LaunchFailed(str(e))
        os.close(w_fd)
        started = self._read_event(r_fd, "started", config.START_TIMEOUT_S)
        if not started:
            err = self._drain(r_fd)
            proc.kill(); proc.wait(); log.close(); os.close(r_fd)
            self._set_state(cid, State.FAILED)
            self.db.event("start", "failed", cid, events=err)
            raise LaunchFailed("launcher did not report a started event", events=err)
        pid = started["host_pid"]
        wid = self.db.execute(
            "INSERT INTO workloads(container_id,type,params_json,limits_json,started_at,host_pid) VALUES(?,?,?,?,?,?)",
            (cid, spec.type.value, spec.model_dump_json(), row["limits_json"], time.time(), pid))
        self._set_state(cid, State.RUNNING, host_pid=pid, pid_starttime=metrics.starttime_of(pid), current_workload=wid)
        self.db.event("start", "ok", cid, workload=spec.type.value, host_pid=pid, cgroup=bool(started.get("cgroup_attached")))
        t = threading.Thread(target=self._supervise, args=(cid, wid, proc, r_fd, log, cg, base, pid), daemon=True)
        self._threads[cid] = t
        t.start()
        return self.get(cid)

    @staticmethod
    def _read_event(fd: int, name: str, timeout: float) -> Optional[dict]:
        end, buf = time.time() + timeout, b""
        while time.time() < end:
            ready, _, _ = select.select([fd], [], [], 0.1)
            if ready:
                chunk = os.read(fd, 4096)
                if not chunk:
                    return None
                buf += chunk
                for line in buf.splitlines():
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    if ev.get("event") == name:
                        return ev
                    if ev.get("event") == "error":
                        return None
        return None

    @staticmethod
    def _drain(fd: int) -> list:
        out = b""
        try:
            while True:
                r, _, _ = select.select([fd], [], [], 0.2)
                if not r:
                    break
                c = os.read(fd, 4096)
                if not c:
                    break
                out += c
        except OSError:
            pass
        evs = []
        for ln in out.splitlines():
            try:
                evs.append(json.loads(ln))
            except ValueError:
                pass
        return evs

    def _supervise(self, cid, wid, proc, r_fd, log, cg, base, pid):
        buf = deque(maxlen=config.MAX_LOG_BYTES // 100)
        self.samples[cid] = buf
        prev_usage, prev_t, killed_for_size = None, None, False
        while proc.poll() is None:
            now = time.time()
            try:
                if cg and Path(cg.path).exists():
                    s = cg.stats()
                    cpu = None
                    if s["usage_usec"] is not None and prev_usage is not None and now > prev_t:
                        cpu = round((s["usage_usec"] - prev_usage) / ((now - prev_t) * 1e6) * 100, 2)
                    prev_usage, prev_t = s["usage_usec"], now
                    smp = {"ts": now, "cpu_percent": cpu, "mem_bytes": s["memory_current"], "pids": s["pids_current"], "source": "cgroup"}
                else:
                    u = metrics.tree_usage(pid)
                    cpu = None
                    if prev_usage is not None and now > prev_t:
                        cpu = round((u["cpu_usec"] - prev_usage) / ((now - prev_t) * 1e6) * 100, 2)
                    prev_usage, prev_t = u["cpu_usec"], now
                    smp = {"ts": now, "cpu_percent": cpu, "mem_bytes": u["rss_bytes"], "pids": u["pids"], "source": "proc-rss"}
                buf.append(smp)
                self.db.execute("INSERT INTO samples(workload_id,ts,cpu_percent,mem_bytes,pids,source) VALUES(?,?,?,?,?,?)",
                                (wid, now, smp["cpu_percent"], smp["mem_bytes"], smp["pids"], smp["source"]))
                if log.tell() > config.MAX_LOG_BYTES:
                    killed_for_size = True
                    self._kill_tree(cid, cg, pid)
            except Exception:  # noqa: BLE001 - sampling must never kill the supervisor
                pass
            time.sleep(config.SAMPLE_INTERVAL_S)
        rc = proc.wait()
        events = self._drain(r_fd)
        os.close(r_fd)
        log.close()
        ex = next((e for e in events if e.get("event") == "exit"), {})
        after = cg.stats() if cg and Path(cg.path).exists() else {}
        oom = (after.get("mem_events", {}).get("oom_kill", 0) - base.get("mem_events", {}).get("oom_kill", 0)) if cg else None
        stopped = cid in self._stop_req
        self._stop_req.discard(cid)
        if killed_for_size:
            reason = "output_limit_exceeded"
        elif stopped:
            reason = "stopped_by_user"
        elif ex.get("timeout"):
            reason = "timeout"
        elif oom and oom > 0:
            reason = "oom_killed"
        elif rc == 0:
            reason = "completed"
        elif any(e.get("event") == "error" for e in events):
            reason = "launcher_error"
        else:
            reason = "exited_nonzero"
        try:
            tail = (config.LOG_DIR / f"{cid}.log").read_bytes()[-2000:].decode(errors="replace")
        except OSError:
            tail = ""
        errs = [e for e in events if e.get("event") in ("error", "warning")]
        started_at = self.db.one("SELECT started_at FROM workloads WHERE id=?", (wid,))["started_at"]
        left = []
        if cg and Path(cg.path).exists():
            left = cg.pids()
            if left:
                cg.kill_all()
        self.db.execute(
            "UPDATE workloads SET ended_at=?,exit_code=?,termination_reason=?,duration_s=?,peak_memory_bytes=?,cpu_usec=?,"
            "nr_throttled=?,throttled_usec=?,oom_kills=?,output_tail=?,errors=? WHERE id=?",
            (time.time(), rc, reason, round(time.time() - started_at, 3), after.get("memory_peak"),
             (after.get("usage_usec") or 0) - (base.get("usage_usec") or 0) if cg else None,
             (after.get("nr_throttled", 0) - base.get("nr_throttled", 0)) if cg else None,
             (after.get("throttled_usec", 0) - base.get("throttled_usec", 0)) if cg else None,
             oom, tail, json.dumps(errs) if errs else None, wid))
        try:
            cur = State(self._row(cid)["state"])
            if cur in (State.RUNNING, State.STOPPING):
                self._set_state(cid, State.STOPPED, host_pid=None, pid_starttime=None)
        except NotFound:
            pass
        self.db.event("workload_end", "ok", cid, reason=reason, exit_code=rc, leftover_pids_killed=left)

    def _kill_tree(self, cid, cg, pid):
        if cg and Path(cg.path).exists():
            cg.kill_all()
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except OSError:
            pass

    def stop(self, cid: str) -> dict:
        row = self._row(cid)
        self._set_state(cid, State.STOPPING)
        self._stop_req.add(cid)
        cg = self._cg(row)
        pid = row.get("host_pid")
        if pid and self._pid_alive(row):
            for p in (pid,):
                try:
                    os.kill(p, signal.SIGKILL)         # ns init (or workload) dies => PID ns torn down
                except OSError:
                    pass
        if cg and Path(cg.path).exists():
            cg.kill_all()
        t = self._threads.get(cid)
        if t:
            t.join(10)
        else:                                          # no supervisor (e.g. after backend restart)
            self._set_state(cid, State.STOPPED, host_pid=None, pid_starttime=None)
        return self.get(cid)

    def wait(self, cid: str, timeout: float = 300) -> dict:
        t = self._threads.get(cid)
        if t:
            t.join(timeout)
        return self.get(cid)

    def remove(self, cid: str) -> None:
        row = self._row(cid)
        if State(row["state"]) not in REMOVABLE:
            raise InvalidTransition(f"cannot remove a {row['state']} container; stop it first")
        cg = self._cg(row)
        ok = cg.remove() if cg else True
        self.db.execute("DELETE FROM containers WHERE id=?", (cid,))
        self.db.event("remove", "ok" if ok else "cgroup_dir_left_behind", cid)
        try:
            (config.LOG_DIR / f"{cid}.log").unlink()
        except OSError:
            pass
        self.samples.pop(cid, None)
        self._threads.pop(cid, None)

    # ---------- observation ----------
    def processes(self, cid: str) -> list[dict]:
        row = self._row(cid)
        cg = self._cg(row)
        pids: list[int] = []
        if cg and Path(cg.path).exists():
            pids = cg.pids()
        elif row.get("host_pid") and self._pid_alive(row):
            pids = metrics.descendants(row["host_pid"])
        return [i for i in (metrics.proc_info(p) for p in pids) if i]

    def current_metrics(self, cid: str) -> dict:
        row = self._row(cid)
        cg = self._cg(row)
        return {"container": cid, "state": row["state"], "cgroup": cg.stats() if cg and Path(cg.path).exists() else None,
                "effective_limits": cg.effective() if cg and Path(cg.path).exists() else None,
                "samples": list(self.samples.get(cid, []))[-300:]}

    def logs(self, cid: str, tail: int = 20000) -> str:
        self._row(cid)
        p = config.LOG_DIR / f"{cid}.log"
        return p.read_bytes()[-tail:].decode(errors="replace") if p.exists() else ""

    def workloads(self, cid: str) -> list[dict]:
        return self.db.query("SELECT * FROM workloads WHERE container_id=? ORDER BY id DESC LIMIT 100", (cid,))
