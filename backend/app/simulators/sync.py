"""Synchronization lab. race_interleaving + dining philosophers are deterministic SIMULATIONS;
producer_consumer runs real threads with real semaphores."""
import threading
from collections import deque


def race_interleaving(schedule: str = "interleaved", increments: int = 3) -> dict:
    """Two threads each do counter++ `increments` times as load/add/store. Schedules: 'serial' or 'interleaved'."""
    counter, steps = 0, []
    regs = {"A": None, "B": None}
    prog = {"A": [], "B": []}
    for t in "AB":
        prog[t] = ["load", "add", "store"] * increments
    pc = {"A": 0, "B": 0}
    order = []
    if schedule == "serial":
        order = ["A"] * len(prog["A"]) + ["B"] * len(prog["B"])
    elif schedule == "interleaved":
        for k in range(len(prog["A"])):
            order += ["A", "B"]
    else:
        raise ValueError("schedule must be serial or interleaved")
    for t in order:
        op = prog[t][pc[t]]; pc[t] += 1
        if op == "load": regs[t] = counter
        elif op == "add": regs[t] += 1
        else: counter = regs[t]
        steps.append({"thread": t, "op": op, "reg": regs[t], "counter": counter})
    return {"schedule": schedule, "expected": 2 * increments, "final": counter, "race_detected": counter != 2 * increments,
            "steps": steps, "is_simulation": True,
            "explanation": "A lost update occurs when both threads load the same value before either stores; a mutex around load-add-store makes the sequence atomic."}


def producer_consumer(capacity: int = 3, items: int = 20) -> dict:
    if not (1 <= capacity <= 64 and 1 <= items <= 1000):
        raise ValueError("capacity 1..64, items 1..1000")
    buf, mutex = deque(), threading.Lock()
    empty, full = threading.Semaphore(capacity), threading.Semaphore(0)
    consumed, max_len = [], [0]

    def prod():
        for i in range(items):
            empty.acquire()
            with mutex:
                buf.append(i); max_len[0] = max(max_len[0], len(buf))
            full.release()

    def cons():
        for _ in range(items):
            full.acquire()
            with mutex:
                consumed.append(buf.popleft())
            empty.release()
    ts = [threading.Thread(target=prod), threading.Thread(target=cons)]
    [t.start() for t in ts]; [t.join(10) for t in ts]
    return {"produced": items, "consumed": len(consumed), "in_order": consumed == list(range(items)),
            "max_buffer_len": max_len[0], "capacity": capacity, "bound_respected": max_len[0] <= capacity, "is_simulation": False}


def dining_philosophers(n: int = 5, strategy: str = "naive") -> dict:
    """Deterministic round: every philosopher acts in lock-step. naive = all take left fork first => circular wait."""
    if n < 2:
        raise ValueError("n >= 2")
    forks = [None] * n
    log = []
    for p in range(n):
        left, right = p, (p + 1) % n
        first, second = (left, right) if strategy == "naive" else (min(left, right), max(left, right))
        if strategy not in ("naive", "ordered"):
            raise ValueError("strategy naive|ordered")
        if forks[first] is None:
            forks[first] = p; log.append(f"P{p} takes fork {first}")
    blocked, eaters = [], []
    for p in range(n):
        left, right = p, (p + 1) % n
        first, second = (left, right) if strategy == "naive" else (min(left, right), max(left, right))
        if forks[first] != p:
            blocked.append(p); continue
        if forks[second] is None:
            forks[second] = p; eaters.append(p); log.append(f"P{p} takes fork {second} and eats")
        else:
            blocked.append(p); log.append(f"P{p} waits for fork {second} (held by P{forks[second]})")
    return {"strategy": strategy, "eating": eaters, "waiting": blocked, "deadlock": not eaters, "log": log, "is_simulation": True,
            "explanation": "Naive: all hold their left fork and wait for the right one => circular wait. Ordered acquisition breaks circular wait."}
