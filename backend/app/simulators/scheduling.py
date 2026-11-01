"""CPU scheduling SIMULATOR. Algorithmic model only; it does not affect the Linux scheduler."""
from collections import deque


def _prep(procs):
    out = []
    for i, p in enumerate(procs):
        b = int(p["burst"])
        if b <= 0 or int(p.get("arrival", 0)) < 0:
            raise ValueError(f"process {p.get('pid', i)}: burst must be >0 and arrival >=0")
        out.append({"pid": p.get("pid", f"P{i + 1}"), "arrival": int(p.get("arrival", 0)), "burst": b,
                    "priority": int(p.get("priority", 0)), "idx": i})
    return sorted(out, key=lambda p: (p["arrival"], p["idx"]))


def simulate(algo: str, procs: list[dict], quantum: int = 2, queues: list[int] | None = None) -> dict:
    ps = _prep(procs)
    if not ps:
        raise ValueError("at least one process required")
    n, t = len(ps), 0
    rem = {p["pid"]: p["burst"] for p in ps}
    first, comp, gantt = {}, {}, []

    def run(pid, dur):
        nonlocal t
        first.setdefault(pid, t)
        if gantt and gantt[-1]["pid"] == pid and gantt[-1]["end"] == t:
            gantt[-1]["end"] = t + dur
        else:
            gantt.append({"pid": pid, "start": t, "end": t + dur})
        t += dur
        rem[pid] -= dur
        if rem[pid] == 0:
            comp[pid] = t

    if algo in ("rr", "mlfq"):
        qs = queues or [quantum, quantum * 2, quantum * 4]
        levels = [deque() for _ in qs] if algo == "mlfq" else [deque()]
        i, lvl_of = 0, {p["pid"]: 0 for p in ps}
        while len(comp) < n:
            while i < n and ps[i]["arrival"] <= t:
                levels[0].append(ps[i]["pid"]); i += 1
            q = next((k for k, d in enumerate(levels) if d), None)
            if q is None:
                if i >= n:
                    break
                gantt.append({"pid": "idle", "start": t, "end": ps[i]["arrival"]}); t = ps[i]["arrival"]
                continue
            pid = levels[q].popleft()
            slice_ = (qs[q] if algo == "mlfq" else quantum)
            dur = min(slice_, rem[pid])
            run(pid, dur)
            while i < n and ps[i]["arrival"] <= t:
                levels[0].append(ps[i]["pid"]); i += 1
            if rem[pid] > 0:
                nq = min(q + 1, len(levels) - 1) if algo == "mlfq" else 0
                levels[nq].append(pid)
    else:
        arrived = lambda: [p for p in ps if p["arrival"] <= t and rem[p["pid"]] > 0]  # noqa: E731
        keys = {"fcfs": lambda p: (p["arrival"], p["idx"]),
                "sjf": lambda p: (p["burst"], p["arrival"], p["idx"]),
                "srtf": lambda p: (rem[p["pid"]], p["arrival"], p["idx"]),
                "priority": lambda p: (p["priority"], p["arrival"], p["idx"]),
                "priority_preemptive": lambda p: (p["priority"], p["arrival"], p["idx"])}
        if algo not in keys:
            raise ValueError(f"unknown algorithm '{algo}'")
        preemptive = algo in ("srtf", "priority_preemptive")
        while len(comp) < n:
            ready = arrived()
            if not ready:
                nxt = min(p["arrival"] for p in ps if rem[p["pid"]] > 0)
                gantt.append({"pid": "idle", "start": t, "end": nxt}); t = nxt
                continue
            p = min(ready, key=keys[algo])
            dur = rem[p["pid"]]
            if preemptive:
                later = [q["arrival"] for q in ps if q["arrival"] > t and rem[q["pid"]] > 0]
                if later:
                    dur = min(dur, min(later) - t)
            run(p["pid"], dur)

    table = []
    for p in sorted(ps, key=lambda p: p["idx"]):
        ct, ft = comp[p["pid"]], first[p["pid"]]
        tat = ct - p["arrival"]
        table.append({"pid": p["pid"], "arrival": p["arrival"], "burst": p["burst"], "priority": p["priority"], "start": ft,
                      "completion": ct, "turnaround": tat, "waiting": tat - p["burst"], "response": ft - p["arrival"]})
    avg = lambda k: round(sum(r[k] for r in table) / n, 3)  # noqa: E731
    return {"algorithm": algo, "table": table, "gantt": gantt, "avg_waiting": avg("waiting"), "avg_turnaround": avg("turnaround"),
            "avg_response": avg("response"), "is_simulation": True,
            "explanation": "Preemptive algorithms (SRTF, preemptive priority, RR, MLFQ) may interrupt a running process; non-preemptive ones run each burst to completion."}
