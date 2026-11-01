"""SQLite persistence. Single connection guarded by a lock (WAL mode)."""
import json
import sqlite3
import threading
import time
from typing import Any, Iterable, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS containers(
  id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, state TEXT NOT NULL, created_at REAL NOT NULL,
  limits_json TEXT NOT NULL, ns_json TEXT NOT NULL, cgroup_path TEXT,
  host_pid INTEGER, pid_starttime INTEGER, current_workload INTEGER);
CREATE TABLE IF NOT EXISTS workloads(
  id INTEGER PRIMARY KEY AUTOINCREMENT, container_id TEXT NOT NULL REFERENCES containers(id) ON DELETE CASCADE,
  type TEXT NOT NULL, params_json TEXT NOT NULL, limits_json TEXT NOT NULL,
  started_at REAL NOT NULL, ended_at REAL, exit_code INTEGER, termination_reason TEXT,
  duration_s REAL, peak_memory_bytes INTEGER, cpu_usec INTEGER, nr_throttled INTEGER,
  throttled_usec INTEGER, oom_kills INTEGER, host_pid INTEGER, output_tail TEXT, errors TEXT);
CREATE INDEX IF NOT EXISTS ix_workloads_container ON workloads(container_id);
CREATE TABLE IF NOT EXISTS samples(
  id INTEGER PRIMARY KEY AUTOINCREMENT, workload_id INTEGER NOT NULL REFERENCES workloads(id) ON DELETE CASCADE,
  ts REAL NOT NULL, cpu_percent REAL, mem_bytes INTEGER, pids INTEGER, source TEXT);
CREATE INDEX IF NOT EXISTS ix_samples_workload ON samples(workload_id);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, container_id TEXT, type TEXT NOT NULL,
  outcome TEXT NOT NULL, detail TEXT);
CREATE INDEX IF NOT EXISTS ix_events_ts ON events(ts);
CREATE TABLE IF NOT EXISTS experiments(
  id TEXT PRIMARY KEY, key TEXT NOT NULL, status TEXT NOT NULL, started_at REAL NOT NULL, ended_at REAL,
  progress TEXT, definition_json TEXT NOT NULL, environment_json TEXT NOT NULL, results_json TEXT);
"""

MAX_EVENTS = 5000


class Database:
    def __init__(self, path):
        self._lock = threading.RLock()
        self._c = sqlite3.connect(str(path), check_same_thread=False)
        self._c.row_factory = sqlite3.Row
        with self._lock:
            self._c.execute("PRAGMA journal_mode=WAL")
            self._c.execute("PRAGMA foreign_keys=ON")
            self._c.executescript(SCHEMA)

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        with self._lock:
            cur = self._c.execute(sql, tuple(params))
            self._c.commit()
            return cur.lastrowid

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._c.execute(sql, tuple(params)).fetchall()]

    def one(self, sql: str, params: Iterable[Any] = ()) -> Optional[dict]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def event(self, type_: str, outcome: str, container_id: Optional[str] = None, **detail) -> None:
        self.execute("INSERT INTO events(ts,container_id,type,outcome,detail) VALUES(?,?,?,?,?)",
                     (time.time(), container_id, type_, outcome, json.dumps(detail, default=str)))
        # bounded audit table
        self.execute("DELETE FROM events WHERE id <= (SELECT MAX(id) FROM events) - ?", (MAX_EVENTS,))
