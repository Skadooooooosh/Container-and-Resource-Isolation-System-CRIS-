import csv
import io
import time
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.api.deps import db, experiments, manager
from app.core.models import ContainerCreate, Limits, WorkloadSpec
from app.isolation import capabilities
from app.monitoring import metrics
from app.simulators import deadlock, disk, memory, scheduling, sync
from app.workloads.registry import DESCRIPTIONS

r = APIRouter(prefix="/api")


@r.get("/health")
def health():
    return {"status": "ok", "time": time.time()}


@r.get("/system/capabilities")
def caps(refresh: bool = False):
    return capabilities.detect(force=refresh)


@r.get("/system/metrics")
def host_metrics():
    cs = manager.list()
    return {"host": metrics.host_metrics(),
            "containers": {"total": len(cs), "running": sum(c["state"] == "RUNNING" for c in cs),
                           "stopped_or_failed": sum(c["state"] in ("STOPPED", "FAILED") for c in cs)}}


@r.get("/workloads")
def workload_types():
    return DESCRIPTIONS


@r.get("/containers")
def list_containers():
    return manager.list()


@r.post("/containers", status_code=201)
def create_container(req: ContainerCreate):
    return manager.create(req)


@r.get("/containers/{cid}")
def get_container(cid: str):
    return manager.get(cid)


@r.patch("/containers/{cid}/limits")
def set_limits(cid: str, lim: Limits):
    return manager.update_limits(cid, lim)


@r.post("/containers/{cid}/start", status_code=202)
def start_container(cid: str, spec: WorkloadSpec):
    return manager.start(cid, spec)


@r.post("/containers/{cid}/stop")
def stop_container(cid: str):
    return manager.stop(cid)


@r.delete("/containers/{cid}", status_code=204)
def remove_container(cid: str):
    manager.remove(cid)


@r.get("/containers/{cid}/processes")
def processes(cid: str):
    return manager.processes(cid)


@r.get("/containers/{cid}/metrics")
def container_metrics(cid: str):
    return manager.current_metrics(cid)


@r.get("/containers/{cid}/metrics.csv", response_class=PlainTextResponse)
def metrics_csv(cid: str):
    w = io.StringIO()
    cw = csv.writer(w)
    cw.writerow(["workload_id", "ts", "cpu_percent", "mem_bytes", "pids", "source"])
    for s in db.query("SELECT workload_id,ts,cpu_percent,mem_bytes,pids,source FROM samples WHERE workload_id IN "
                      "(SELECT id FROM workloads WHERE container_id=?) ORDER BY ts", (cid,)):
        cw.writerow(s.values())
    return w.getvalue()


@r.get("/containers/{cid}/logs", response_class=PlainTextResponse)
def logs(cid: str):
    return manager.logs(cid)


@r.get("/containers/{cid}/workloads")
def workload_history(cid: str):
    return manager.workloads(cid)


@r.get("/events")
def events(limit: int = Query(100, le=1000), container_id: Optional[str] = None, q: Optional[str] = None):
    sql, p = "SELECT * FROM events WHERE 1=1", []
    if container_id:
        sql += " AND container_id=?"; p.append(container_id)
    if q:
        sql += " AND (type LIKE ? OR detail LIKE ?)"; p += [f"%{q}%", f"%{q}%"]
    return db.query(sql + " ORDER BY id DESC LIMIT ?", [*p, limit])


class ExperimentRun(BaseModel):
    key: str
    runs: Optional[int] = Field(None, ge=1, le=10)


@r.get("/experiments/definitions")
def exp_defs():
    return experiments.definitions()


@r.get("/experiments")
def exp_list():
    return experiments.list()


@r.post("/experiments", status_code=202)
def exp_run(req: ExperimentRun):
    return {"id": experiments.start(req.key, req.runs)}


@r.get("/experiments/{eid}")
def exp_get(eid: str):
    return experiments.get(eid)


@r.get("/experiments/{eid}/results.json")
def exp_results(eid: str):
    return experiments.get(eid)["results"]


# ---- OS laboratory (all simulations; responses carry is_simulation=true unless real threads are used) ----
class SchedReq(BaseModel):
    algorithm: str
    processes: list[dict]
    quantum: int = Field(2, ge=1)


class PageReq(BaseModel):
    algorithm: str
    references: list[int]
    frames: int = Field(3, ge=1, le=64)


class TransReq(BaseModel):
    addresses: list[int]
    page_size: int = 1024
    page_table: dict[int, int]
    tlb_size: int = 0


class BankerReq(BaseModel):
    available: list[int]
    maximum: list[list[int]]
    allocation: list[list[int]]
    request_pid: Optional[int] = None
    request: Optional[list[int]] = None


class DetectReq(BaseModel):
    available: list[int]
    allocation: list[list[int]]
    request: list[list[int]]


class DiskReq(BaseModel):
    algorithm: str
    requests: list[int]
    head: int
    disk_size: int = 200
    direction: str = "up"


@r.post("/lab/scheduling")
def lab_sched(q: SchedReq):
    return scheduling.simulate(q.algorithm, q.processes, q.quantum)


@r.post("/lab/memory/replacement")
def lab_repl(q: PageReq):
    return memory.replace(q.algorithm, q.references, q.frames)


@r.post("/lab/memory/translate")
def lab_trans(q: TransReq):
    return memory.translate(q.addresses, q.page_size, q.page_table, q.tlb_size)


@r.post("/lab/deadlock/banker")
def lab_banker(q: BankerReq):
    if q.request_pid is not None and q.request is not None:
        return deadlock.request(q.request_pid, q.request, q.available, q.maximum, q.allocation)
    return deadlock.safety(q.available, q.maximum, q.allocation)


@r.post("/lab/deadlock/detect")
def lab_detect(q: DetectReq):
    return deadlock.detect(q.available, q.allocation, q.request)


@r.post("/lab/deadlock/wait-for")
def lab_wfg(edges: list[list[str]]):
    return deadlock.wait_for_cycle(edges)


@r.post("/lab/disk-scheduling")
def lab_disk(q: DiskReq):
    return disk.schedule(q.algorithm, q.requests, q.head, q.disk_size, q.direction)


@r.get("/lab/synchronization/race")
def lab_race(schedule: str = "interleaved", increments: int = Query(3, ge=1, le=20)):
    return sync.race_interleaving(schedule, increments)


@r.get("/lab/synchronization/producer-consumer")
def lab_pc(capacity: int = Query(3, ge=1, le=64), items: int = Query(20, ge=1, le=1000)):
    return sync.producer_consumer(capacity, items)


@r.get("/lab/synchronization/dining-philosophers")
def lab_dp(n: int = Query(5, ge=2, le=20), strategy: str = "naive"):
    return sync.dining_philosophers(n, strategy)
