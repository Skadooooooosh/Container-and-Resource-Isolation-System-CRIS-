import os
import sys
import time
import json
import errno
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.containers.states import State
from app.core import config
from app.core.errors import InvalidTransition, LaunchFailed, PermissionDenied, Unsupported
from app.core.models import ContainerCreate, Limits, WorkloadSpec, WorkloadType
from app.database.db import Database
from app.containers.manager import ContainerManager
from app.resources.cgroups import Cgroup
from app.isolation import capabilities
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test.db"
    return Database(db_file)


@pytest.fixture
def test_mgr(test_db):
    return ContainerManager(test_db)


# 1. Valid container creation
def test_valid_container_creation(client):
    name = f"c-valid-{int(time.time()*1000)%100000}"
    resp = client.post("/api/containers", json={
        "name": name,
        "limits": {"cpu_quota_percent": 50, "memory_mb": 128, "pids_max": 20},
        "namespaces": {"pid": True, "mnt": True, "uts": True, "ipc": True, "net": False}
    })
    # If cgroup delegation is unavailable on this host, it returns 422 Unsupported (honest)
    # If without limits, it succeeds 201
    if resp.status_code == 422 and "cgroup" in resp.json()["error"]["message"]:
        # Try without cgroup limits
        resp = client.post("/api/containers", json={"name": name})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == name
    assert data["state"] == "CREATED"
    assert "id" in data
    # Clean up
    client.delete(f"/api/containers/{data['id']}")


# 2. Duplicate container names
def test_duplicate_container_name(client):
    name = f"c-dup-{int(time.time()*1000)%100000}"
    r1 = client.post("/api/containers", json={"name": name})
    assert r1.status_code == 201
    cid = r1.json()["id"]

    r2 = client.post("/api/containers", json={"name": name})
    assert r2.status_code == 409
    assert "already exists" in r2.json()["error"]["message"]

    client.delete(f"/api/containers/{cid}")


# 3. Invalid configurations
def test_invalid_configurations(client):
    # Bad container names
    assert client.post("/api/containers", json={"name": ""}).status_code == 422
    assert client.post("/api/containers", json={"name": "invalid name with spaces"}).status_code == 422
    assert client.post("/api/containers", json={"name": "a" * 45}).status_code == 422
    assert client.post("/api/containers", json={"name": "-starts-with-dash"}).status_code == 422

    # Invalid limits
    assert client.post("/api/containers", json={"name": "c-badlim", "limits": {"cpu_quota_percent": 0}}).status_code == 422
    assert client.post("/api/containers", json={"name": "c-badlim", "limits": {"cpu_quota_percent": 500}}).status_code == 422
    assert client.post("/api/containers", json={"name": "c-badlim", "limits": {"memory_mb": 4}}).status_code == 422
    assert client.post("/api/containers", json={"name": "c-badlim", "limits": {"pids_max": 1}}).status_code == 422

    # Invalid workload params
    assert client.post("/api/containers/nonexistent/start", json={"type": "invalid_type"}).status_code == 422
    assert client.post("/api/containers/nonexistent/start", json={"type": "cpu", "seconds": 0}).status_code == 422
    assert client.post("/api/containers/nonexistent/start", json={"type": "cpu", "seconds": 200}).status_code == 422


# 4. Start and stop lifecycle (mocked launcher)
def test_start_and_stop_lifecycle(test_mgr):
    req = ContainerCreate(name="c-lifecycle")
    c = test_mgr.create(req)
    cid = c["id"]
    assert c["state"] == State.CREATED.value

    # Simulate launcher startup and exit
    with patch("app.containers.manager.config.CRIS_RUN") as mock_bin, \
         patch("app.containers.manager.capabilities.validate_requested_namespaces", return_value=(True, "ok", None)), \
         patch("app.containers.manager.Popen") as mock_popen, \
         patch.object(ContainerManager, "_read_startup", return_value=({"event": "started", "host_pid": 99999, "cgroup_attached": False}, [])):

        mock_bin.exists.return_value = True
        proc_mock = MagicMock()
        proc_mock.poll.return_value = None
        def kill_action():
            proc_mock.poll.return_value = 0
            proc_mock.wait.return_value = 0
        proc_mock.kill.side_effect = kill_action
        proc_mock.wait.return_value = 0
        mock_popen.return_value = proc_mock

        with patch("app.containers.manager.metrics.starttime_of", return_value=12345), \
             patch("os.kill", side_effect=lambda p, s: kill_action()):
            started = test_mgr.start(cid, WorkloadSpec(type=WorkloadType.idle, seconds=5))
            assert started["state"] == State.RUNNING.value
            assert started["host_pid"] == 99999

            # Stop
            stopped = test_mgr.stop(cid)
            assert stopped["state"] == State.STOPPED.value
            assert stopped["host_pid"] is None

    test_mgr.remove(cid)


# 5. Repeated stop requests
def test_repeated_stop_requests(test_mgr):
    req = ContainerCreate(name="c-repstop")
    c = test_mgr.create(req)
    cid = c["id"]

    # Stopping a created container is idempotent
    s1 = test_mgr.stop(cid)
    assert s1["id"] == cid

    # Transition to STOPPED manually
    test_mgr._set_state(cid, State.STARTING)
    test_mgr._set_state(cid, State.RUNNING)
    test_mgr._set_state(cid, State.STOPPING)
    test_mgr._set_state(cid, State.STOPPED)

    # Calling stop on already STOPPED container must succeed idempotently
    s2 = test_mgr.stop(cid)
    assert s2["state"] == State.STOPPED.value

    s3 = test_mgr.stop(cid)
    assert s3["state"] == State.STOPPED.value

    test_mgr.remove(cid)


# 6. Unsupported namespace combinations
def test_unsupported_namespace_combinations(test_mgr):
    req = ContainerCreate(name="c-unsup-ns")
    c = test_mgr.create(req)
    cid = c["id"]

    # When capability detection says combined namespaces fail with EPERM
    with patch("app.containers.manager.config.CRIS_RUN") as mock_bin, \
         patch("app.containers.manager.capabilities.validate_requested_namespaces",
               return_value=(False, "Combined namespace creation is blocked: EPERM", errno.EPERM)):
        mock_bin.exists.return_value = True
        with pytest.raises(PermissionDenied) as exc:
            test_mgr.start(cid, WorkloadSpec(type=WorkloadType.cpu, seconds=2))
        assert exc.value.status == 403
        assert "Permission denied" in exc.value.message

    # Container state must be FAILED, not left in STARTING
    assert test_mgr.get(cid)["state"] == State.FAILED.value
    test_mgr.remove(cid)


# 7. Native launcher error propagation
def test_native_launcher_error_propagation(test_mgr):
    req = ContainerCreate(name="c-errprop")
    c = test_mgr.create(req)
    cid = c["id"]

    # Launcher emits an explicit error event
    mock_events = [{"event": "error", "stage": "clone", "errno": errno.EPERM, "msg": "Operation not permitted"}]

    with patch("app.containers.manager.config.CRIS_RUN") as mock_bin, \
         patch("app.containers.manager.capabilities.validate_requested_namespaces", return_value=(True, "ok", None)), \
         patch("app.containers.manager.Popen") as mock_popen, \
         patch.object(ContainerManager, "_read_startup", return_value=(None, mock_events)):

        mock_bin.exists.return_value = True
        proc_mock = MagicMock()
        proc_mock.poll.return_value = 1
        proc_mock.returncode = 4
        mock_popen.return_value = proc_mock

        with pytest.raises(PermissionDenied) as exc:
            test_mgr.start(cid, WorkloadSpec(type=WorkloadType.cpu, seconds=2))

        # Check that stage and error message were NOT discarded
        assert "Operation not permitted" in exc.value.message
        assert exc.value.detail.get("stage") == "clone"
        assert exc.value.detail.get("errno") == errno.EPERM

    # Verify event was logged to db
    events = test_mgr.db.query("SELECT * FROM events WHERE container_id=? AND outcome='failed'", (cid,))
    assert len(events) >= 1
    assert "Operation not permitted" in events[0]["detail"]

    test_mgr.remove(cid)


# 8, 9, 10. CPU, Memory, PID resource enforcement
def test_cgroup_resource_enforcement_confirmation(tmp_path):
    cg_path = tmp_path / "cris-testcg"
    cg_path.mkdir()
    (cg_path / "cgroup.controllers").write_text("cpu memory pids")
    (cg_path / "cpu.max").write_text("50000 100000")
    (cg_path / "memory.max").write_text(str(64 * 1024 * 1024))
    (cg_path / "pids.max").write_text("25")

    cg = Cgroup(cg_path)

    # Effective values match -> returns effective dict
    eff = cg.set_limits(Limits(cpu_quota_percent=50, memory_mb=64, pids_max=25))
    assert eff["cpu_quota_percent"] == 50.0
    assert eff["memory_mb"] == 64
    assert eff["pids_max"] == 25

    # If kernel rejected or failed to enforce CPU quota:
    with patch.object(Cgroup, "effective", return_value={"cpu_quota_percent": 100.0, "memory_mb": 64, "pids_max": 25}):
        with pytest.raises(Unsupported) as exc_cpu:
            cg.set_limits(Limits(cpu_quota_percent=50))
        assert "did not confirm CPU quota" in exc_cpu.value.message

    # If kernel rejected memory limit:
    with patch.object(Cgroup, "effective", return_value={"cpu_quota_percent": 50.0, "memory_mb": 32, "pids_max": 25}):
        with pytest.raises(Unsupported) as exc_mem:
            cg.set_limits(Limits(memory_mb=64))
        assert "did not confirm memory limit" in exc_mem.value.message

    # If kernel rejected pids limit:
    with patch.object(Cgroup, "effective", return_value={"cpu_quota_percent": 50.0, "memory_mb": 64, "pids_max": 10}):
        with pytest.raises(Unsupported) as exc_pids:
            cg.set_limits(Limits(pids_max=25))
        assert "did not confirm pids limit" in exc_pids.value.message


# 11. Cleanup after failed startup
def test_cleanup_after_failed_startup(test_mgr):
    req = ContainerCreate(name="c-cleanup-fail")
    c = test_mgr.create(req)
    cid = c["id"]

    with patch("app.containers.manager.config.CRIS_RUN") as mock_bin, \
         patch("app.containers.manager.capabilities.validate_requested_namespaces", return_value=(True, "ok", None)), \
         patch("app.containers.manager.Popen") as mock_popen, \
         patch.object(ContainerManager, "_read_startup", return_value=(None, [])):

        mock_bin.exists.return_value = True
        proc_mock = MagicMock()
        proc_mock.poll.return_value = 1
        proc_mock.returncode = 127
        mock_popen.return_value = proc_mock

        with pytest.raises(LaunchFailed):
            test_mgr.start(cid, WorkloadSpec(type=WorkloadType.cpu, seconds=2))

        # Check proc was killed and waited
        assert proc_mock.kill.called
        assert proc_mock.wait.called
        # Container must not be in _threads
        assert cid not in test_mgr._threads
        # State must be FAILED
        assert test_mgr.get(cid)["state"] == State.FAILED.value

    test_mgr.remove(cid)


# 12. Orphan process detection on reconcile
def test_orphan_process_detection(test_mgr):
    # Insert a container marked RUNNING with an alive PID
    my_pid = os.getpid()
    with patch("app.containers.manager.metrics.starttime_of", return_value=9999):
        test_mgr.db.execute(
            "INSERT INTO containers(id,name,state,created_at,limits_json,ns_json,host_pid,pid_starttime) "
            "VALUES(?,?,?,?,?,?,?,?)",
            ("c-orphan", "c-orphan", State.RUNNING.value, time.time(), "{}", "{}", my_pid, 9999)
        )
        test_mgr.reconcile()
        # Still RUNNING because PID is alive
        row = test_mgr.get("c-orphan")
        assert row["state"] == State.RUNNING.value
        ev = test_mgr.db.query("SELECT * FROM events WHERE container_id='c-orphan' AND type='reconcile'")
        assert any(e["outcome"] == "orphan_running" for e in ev)


# 13. Application restart recovery (stale workloads)
def test_application_restart_recovery(test_mgr):
    # Insert a container marked RUNNING with a dead PID (e.g. PID 999999)
    test_mgr.db.execute(
        "INSERT INTO containers(id,name,state,created_at,limits_json,ns_json,host_pid,pid_starttime) "
        "VALUES(?,?,?,?,?,?,?,?)",
        ("c-stale", "c-stale", State.RUNNING.value, time.time() - 100, "{}", "{}", 999999, 1111)
    )
    # Insert an unclosed workload
    test_mgr.db.execute(
        "INSERT INTO workloads(id,container_id,type,params_json,limits_json,started_at,host_pid) "
        "VALUES(?,?,?,?,?,?,?)",
        (101, "c-stale", "cpu", "{}", "{}", time.time() - 100, 999999)
    )

    with patch("app.containers.manager.metrics.starttime_of", return_value=None):
        test_mgr.reconcile()

    # Container must be transitioned to FAILED
    row = test_mgr.get("c-stale")
    assert row["state"] == State.FAILED.value
    assert row["host_pid"] is None

    # Workload must be marked ended with reason 'lost_on_restart'
    wl = test_mgr.db.one("SELECT * FROM workloads WHERE id=101")
    assert wl["ended_at"] is not None
    assert wl["termination_reason"] == "lost_on_restart"
    assert wl["exit_code"] == 1


# 14. Concurrent container creation
def test_concurrent_container_creation(test_mgr):
    created_ids = []
    errors = []

    def create_worker(index):
        try:
            req = ContainerCreate(name=f"c-conc-{index}")
            res = test_mgr.create(req)
            created_ids.append(res["id"])
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=create_worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(created_ids) == 10
    assert len(set(created_ids)) == 10

    # Clean up
    for cid in created_ids:
        test_mgr.remove(cid)


# 15. Interrupted experiments
def test_interrupted_experiments(test_mgr):
    from app.experiments.engine import ExperimentEngine
    engine = ExperimentEngine(test_mgr.db, test_mgr)

    # 1) When capabilities are missing (e.g. on Windows), start() refuses with Unsupported
    if sys.platform != "linux":
        with pytest.raises(Unsupported):
            engine.start("cpu-comparison")

    # 2) If an experiment thread crashes / is interrupted mid-run
    eid = "x-test-crash"
    test_mgr.db.execute(
        "INSERT INTO experiments(id,key,status,started_at,progress,definition_json,environment_json) VALUES(?,?,?,?,?,?,?)",
        (eid, "cpu-comparison", "running", time.time(), "0", "{}", "{}")
    )
    # Simulate exception inside _run
    with patch.object(engine, "_one", side_effect=RuntimeError("Container daemon crash")):
        engine._run(eid, "cpu-comparison", 1)

    exp_row = test_mgr.db.one("SELECT * FROM experiments WHERE id=?", (eid,))
    assert exp_row["status"] == "failed"
    res = json.loads(exp_row["results_json"])
    assert "error" in res
    assert "Container daemon crash" in res["error"]


# 16. Invalid OS simulator inputs
def test_invalid_os_simulator_inputs(client):
    # CPU Scheduling: empty process list
    r = client.post("/api/lab/scheduling", json={"algorithm": "fcfs", "processes": []})
    assert r.status_code == 422

    # CPU Scheduling: negative burst
    r = client.post("/api/lab/scheduling", json={"algorithm": "fcfs", "processes": [{"pid": "P1", "burst": -5}]})
    assert r.status_code == 422

    # CPU Scheduling: unknown algorithm
    r = client.post("/api/lab/scheduling", json={"algorithm": "magic_scheduler", "processes": [{"pid": "P1", "burst": 5}]})
    assert r.status_code == 422

    # Paging: frames <= 0
    r = client.post("/api/lab/memory/replacement", json={"algorithm": "fifo", "frames": 0, "references": [1, 2, 3]})
    assert r.status_code == 422

    # Paging: empty references
    r = client.post("/api/lab/memory/replacement", json={"algorithm": "fifo", "frames": 3, "references": []})
    assert r.status_code == 422

    # Banker's algorithm: dimension mismatch
    r = client.post("/api/lab/deadlock/banker", json={
        "available": [3, 3, 2],
        "maximum": [[7, 5, 3], [3, 2, 2]],
        "allocation": [[0, 1, 0]]  # Only 1 process in allocation, 2 in maximum
    })
    assert r.status_code == 422

    # Disk scheduling: head position out of bounds
    r = client.post("/api/lab/disk-scheduling", json={
        "algorithm": "look",
        "head": 500,
        "disk_size": 200,
        "direction": "up",
        "requests": [10, 20]
    })
    assert r.status_code == 422


# 17. Host Metrics - Windows, Linux mock, and API endpoint verification
def test_host_metrics_windows_or_current(client):
    from app.monitoring import metrics
    m = metrics.host_metrics()
    assert isinstance(m, dict)
    assert "ts" in m
    assert "cpus" in m
    assert m["cpus"] > 0
    assert "source" in m

    # Endpoint must return 200 with valid structure
    res = client.get("/api/system/metrics")
    assert res.status_code == 200
    body = res.json()
    assert "host" in body
    assert "containers" in body
    assert body["host"]["cpus"] > 0


def test_host_metrics_linux_mock():
    from app.monitoring import metrics

    fake_stat = "cpu  2255 34 2290 22625563 6290 127 456 0 0 0\n"
    fake_meminfo = (
        "MemTotal:       16384000 kB\n"
        "MemFree:         4096000 kB\n"
        "MemAvailable:    8192000 kB\n"
    )

    def fake_read_text(self, *args, **kwargs):
        p_str = str(self).replace("\\", "/")
        if "proc/stat" in p_str:
            return fake_stat
        if "proc/meminfo" in p_str:
            return fake_meminfo
        raise FileNotFoundError(f"No such file: {self}")

    with patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "read_text", new=fake_read_text):
        m = metrics.host_metrics()
        assert m["source"] == "/proc/stat,/proc/meminfo"
        assert m["mem_total_bytes"] == 16384000 * 1024
        assert m["mem_used_bytes"] == (16384000 - 8192000) * 1024
        assert m["mem_percent"] == 50.0


def test_host_metrics_unsupported_platform():
    from app.monitoring import metrics
    with patch.object(Path, "exists", return_value=False), \
         patch("sys.platform", "darwin"):
        m = metrics.host_metrics()
        assert m["source"] == "unsupported platform"
        assert m["cpu_percent"] is None
        assert m["mem_total_bytes"] is None

