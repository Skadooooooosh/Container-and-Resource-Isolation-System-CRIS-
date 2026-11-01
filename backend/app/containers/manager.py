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
            os.killpg(os.getpgid(pid), SIGKILL)
        except (OSError, AttributeError):
            pass

    def stop(self, cid: str) -> dict:
        row = self._row(cid)
        cur = State(row["state"])
        if cur == State.STOPPED:
            return self.get(cid)
        if cur in (State.CREATED, State.FAILED) and not self._pid_alive(row):
            return self.get(cid)
        if cur == State.STOPPING:
            t = self._threads.get(cid)
            if t:
                t.join(10)
            return self.get(cid)

        self._set_state(cid, State.STOPPING)
        self._stop_req.add(cid)
        cg = self._cg(row)
        pid = row.get("host_pid")
        if pid and self._pid_alive(row):
            for p in (pid,):
                try:
                    os.kill(p, SIGKILL)         # ns init (or workload) dies => PID ns torn down
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