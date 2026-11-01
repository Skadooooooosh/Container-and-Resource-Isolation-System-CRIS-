"""Disk-scheduling algorithm models (not real device behaviour)."""


def schedule(algo: str, requests: list[int], head: int, disk_size: int = 200, direction: str = "up", count_return: bool = True) -> dict:
    if disk_size <= 0 or any(r < 0 or r >= disk_size for r in [*requests, head]):
        raise ValueError("all cylinders must be within 0..disk_size-1")
    up, reqs, order, path = direction == "up", list(requests), [], [head]
    hi, lo = disk_size - 1, 0
    lower, upper = sorted(r for r in reqs if r < head), sorted(r for r in reqs if r >= head)
    if algo == "fcfs":
        order = reqs
    elif algo == "sstf":
        pend, cur = reqs[:], head
        while pend:
            nxt = min(pend, key=lambda r: abs(r - cur)); order.append(nxt); pend.remove(nxt); cur = nxt
    elif algo in ("scan", "look"):
        a, b = (upper, lower[::-1]) if up else (lower[::-1], upper)
        order = a + b
        ends = [(hi if up else lo)] if algo == "scan" else []
        path = _walk(head, a, ends, b)
    elif algo in ("cscan", "clook"):
        a, b = (upper, lower) if up else (lower[::-1], upper[::-1])
        order = a + b
        if algo == "cscan":
            first_end, jump = (hi, lo) if up else (lo, hi)
            path = [head, *a, first_end]
            if count_return:
                path += [jump]
            path += b
        else:
            path = [head, *a, *b]
    else:
        raise ValueError("unknown algorithm")
    if algo in ("fcfs", "sstf"):
        path = [head, *order]
    total = sum(abs(path[i + 1] - path[i]) for i in range(len(path) - 1))
    return {"algorithm": algo, "service_order": order, "head_path": path, "total_movement": total,
            "avg_movement_per_request": round(total / len(reqs), 3) if reqs else 0, "is_simulation": True,
            "note": "Seek-distance model only; real latency depends on hardware, firmware and the OS I/O stack."}


def _walk(head, first, ends, second):
    return [head, *first, *ends, *second]
