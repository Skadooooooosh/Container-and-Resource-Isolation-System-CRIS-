"""oslab - command-line interface. Every command calls the real manager; nothing is faked."""
import argparse
import json
import sys

from app.core.errors import CrisError


def _p(o):
    print(json.dumps(o, indent=2, default=str))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="oslab", description="Container & Resource Isolation System CLI")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("doctor", help="detect namespace/cgroup capabilities")
    c = sp.add_parser("create-container"); c.add_argument("--name", required=True)
    c.add_argument("--cpu", type=float, help="CPU quota percent (100 = 1 CPU)"); c.add_argument("--memory", type=int, help="MiB")
    c.add_argument("--pids", type=int)
    sp.add_parser("list")
    for n in ("inspect", "stats", "stop", "destroy", "logs", "ps"):
        s = sp.add_parser(n); s.add_argument("id")
    r = sp.add_parser("run"); r.add_argument("id"); r.add_argument("--workload", default="cpu", choices=["cpu", "memory", "process", "mixed", "idle", "nsinfo"])
    r.add_argument("--seconds", type=int, default=10); r.add_argument("--mb", type=int, default=64); r.add_argument("--procs", type=int, default=8)
    r.add_argument("--iterations", type=int, default=300_000_000); r.add_argument("--detach", action="store_true")
    lc = sp.add_parser("limit-cpu"); lc.add_argument("id"); lc.add_argument("--quota", type=float, required=True, help="percent")
    lm = sp.add_parser("limit-memory"); lm.add_argument("id"); lm.add_argument("--limit", type=int, required=True, help="MiB")
    e = sp.add_parser("experiment"); es = e.add_subparsers(dest="sub", required=True)
    er = es.add_parser("run"); er.add_argument("key"); er.add_argument("--runs", type=int)
    es.add_parser("list")
    a = ap.parse_args(argv)
    try:
        from app.api.deps import experiments, manager
        from app.core.models import ContainerCreate, Limits, WorkloadSpec
        from app.isolation import capabilities
        if a.cmd == "doctor":
            d = capabilities.detect(force=True)
            print("kernel", d["environment"]["kernel"], d["environment"]["arch"], "euid", d["environment"]["euid"])
            for f in d["features"]:
                print(f"  [{f['status']:<24}] {f['name']}  {f['detail']}")
        elif a.cmd == "create-container":
            _p(manager.create(ContainerCreate(name=a.name, limits=Limits(cpu_quota_percent=a.cpu, memory_mb=a.memory, pids_max=a.pids))))
        elif a.cmd == "list":
            for x in manager.list():
                print(f"{x['id']}  {x['name']:<16} {x['state']:<9} limits={x['limits']}")
        elif a.cmd == "inspect":
            _p(manager.get(a.id))
        elif a.cmd == "stats":
            _p(manager.current_metrics(a.id)["cgroup"])
        elif a.cmd == "ps":
            _p(manager.processes(a.id))
        elif a.cmd == "logs":
            print(manager.logs(a.id))
        elif a.cmd == "stop":
            _p(manager.stop(a.id))
        elif a.cmd == "destroy":
            manager.remove(a.id); print("removed", a.id)
        elif a.cmd == "limit-cpu":
            _p(manager.update_limits(a.id, Limits(cpu_quota_percent=a.quota)))
        elif a.cmd == "limit-memory":
            _p(manager.update_limits(a.id, Limits(memory_mb=a.limit)))
        elif a.cmd == "run":
            manager.start(a.id, WorkloadSpec(type=a.workload, seconds=a.seconds, memory_mb=a.mb, procs=a.procs, iterations=a.iterations))
            if a.detach:
                print("started (note: the supervisor lives in this process; use the API server for detached runs)")
            manager.wait(a.id)
            w = manager.workloads(a.id)[0]
            _p({k: w[k] for k in ("type", "exit_code", "termination_reason", "duration_s", "cpu_usec", "nr_throttled", "throttled_usec", "peak_memory_bytes", "oom_kills")})
            print(manager.logs(a.id)[-800:])
        elif a.cmd == "experiment":
            if a.sub == "list":
                _p(experiments.definitions())
            else:
                import time
                eid = experiments.start(a.key, a.runs)
                print("experiment", eid)
                while (x := experiments.get(eid))["status"] == "running":
                    print("  progress", x["progress"]); time.sleep(1.5)
                _p(x["results"]["summary"] if x["results"] and "summary" in x["results"] else x["results"])
                for n in (x["results"] or {}).get("interpretation", []):
                    print("-", n)
        return 0
    except CrisError as ex:
        print(f"error[{ex.code}]: {ex.message}", file=sys.stderr)
        return 3 if ex.status == 422 else 1


if __name__ == "__main__":
    sys.exit(main())
