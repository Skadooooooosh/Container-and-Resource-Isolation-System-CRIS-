import os
import pytest
import sys
from fastapi.testclient import TestClient
from app.containers.states import State, can_transition
from app.core import config
from app.core.models import ContainerCreate, Limits

native = config.CRIS_RUN.exists() and config.CRIS_WORKLOAD.exists()


def test_state_machine():
    assert can_transition(State.CREATED, State.STARTING)
    assert not can_transition(State.CREATED, State.RUNNING)
    assert not can_transition(State.STOPPED, State.RUNNING)
    assert can_transition(State.STOPPED, State.STARTING)


def test_validation():
    with pytest.raises(ValueError): ContainerCreate(name="bad name!")
    with pytest.raises(ValueError): Limits(memory_mb=1)
    with pytest.raises(ValueError): Limits(cpu_quota_percent=0)
    assert not Limits().any()


@pytest.fixture(scope="module")
def client():
    from app.main import app
    return TestClient(app)


def test_api_basics(client):
    assert client.get("/api/health").json()["status"] == "ok"
    caps = client.get("/api/system/capabilities").json()
    assert {"environment", "features"} <= set(caps) and all("status" in f for f in caps["features"])
    assert client.get("/api/containers/nope").status_code == 404
    assert client.post("/api/containers", json={"name": "bad name"}).status_code == 422
    assert client.post("/api/lab/scheduling", json={"algorithm": "fcfs", "processes": [{"burst": 0}]}).status_code == 422
    assert client.get("/api/lab/synchronization/race").json()["is_simulation"]


@pytest.mark.skipif(sys.platform != "linux", reason="Requires Linux namespaces/cgroups")
@pytest.mark.skipif(not native, reason="native binaries not built (run `make native`)")
def test_integration_real_namespace_isolation(client):
    c = client.post("/api/containers", json={"name": "itest-ns"}).json()
    cid = c["id"]
    assert client.post(f"/api/containers/{cid}/start", json={"type": "nsinfo", "seconds": 1}).status_code == 202
    from app.api.deps import manager
    manager.wait(cid, 20)
    out = client.get(f"/api/containers/{cid}/logs").text
    assert '"hostname":"itest-ns"' in out                       # UTS namespace
    assert '"visible_pids":' in out
    host_pid_ns = os.readlink("/proc/self/ns/pid")
    assert host_pid_ns not in out                              # different PID namespace inode
    assert client.get(f"/api/containers/{cid}").json()["state"] == "STOPPED"
    assert client.delete(f"/api/containers/{cid}").status_code == 204


@pytest.mark.skipif(sys.platform != "linux", reason="Requires Linux namespaces/cgroups")
@pytest.mark.skipif(not native, reason="native binaries not built")
def test_integration_stop_kills_tree(client):
    c = client.post("/api/containers", json={"name": "itest-stop"}).json()
    cid = c["id"]
    client.post(f"/api/containers/{cid}/start", json={"type": "idle", "seconds": 60})
    import time; time.sleep(1)
    assert client.post(f"/api/containers/{cid}/start", json={"type": "idle"}).status_code == 409   # no duplicate workload
    assert client.post(f"/api/containers/{cid}/stop").json()["state"] == "STOPPED"
    time.sleep(0.5)
    assert client.get(f"/api/containers/{cid}/processes").json() == []
    assert client.delete(f"/api/containers/{cid}").status_code == 204
