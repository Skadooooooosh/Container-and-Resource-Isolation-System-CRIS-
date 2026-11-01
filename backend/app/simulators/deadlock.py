"""Deadlock SIMULATOR: Banker's algorithm, matrix detection, wait-for-graph cycle detection."""


def _check(avail, mx, alloc):
    n, m = len(alloc), len(avail)
    if len(mx) != n or any(len(r) != m for r in [*mx, *alloc]):
        raise ValueError("matrix dimensions inconsistent")
    need = [[mx[i][j] - alloc[i][j] for j in range(m)] for i in range(n)]
    if any(v < 0 for r in need for v in r):
        raise ValueError("allocation exceeds declared maximum")
    return need


def safety(avail, mx, alloc) -> dict:
    need = _check(avail, mx, alloc)
    n, work, fin, seq, trace = len(alloc), list(avail), [False] * len(alloc), [], []
    progress = True
    while progress:
        progress = False
        for i in range(n):
            if not fin[i] and all(need[i][j] <= work[j] for j in range(len(work))):
                work = [work[j] + alloc[i][j] for j in range(len(work))]
                fin[i] = True; seq.append(f"P{i}"); progress = True
                trace.append({"process": f"P{i}", "work_after": list(work)})
    return {"safe": all(fin), "safe_sequence": seq if all(fin) else [], "need": need, "trace": trace,
            "unfinished": [f"P{i}" for i, f in enumerate(fin) if not f], "is_simulation": True}


def request(pid: int, req, avail, mx, alloc) -> dict:
    need = _check(avail, mx, alloc)
    if any(req[j] > need[pid][j] for j in range(len(req))):
        return {"granted": False, "reason": "request exceeds declared maximum claim"}
    if any(req[j] > avail[j] for j in range(len(req))):
        return {"granted": False, "reason": "resources not available; process must wait"}
    a2 = [r[:] for r in alloc]; av2 = list(avail)
    for j in range(len(req)):
        a2[pid][j] += req[j]; av2[j] -= req[j]
    s = safety(av2, mx, a2)
    return {"granted": s["safe"], "reason": "resulting state is safe" if s["safe"] else "would leave an unsafe state", "after": s}


def detect(avail, alloc, req) -> dict:
    """Deadlock detection for multi-instance resources (processes whose pending requests can never be satisfied)."""
    n = len(alloc)
    work, fin = list(avail), [all(v == 0 for v in alloc[i]) for i in range(n)]
    changed = True
    while changed:
        changed = False
        for i in range(n):
            if not fin[i] and all(req[i][j] <= work[j] for j in range(len(work))):
                work = [work[j] + alloc[i][j] for j in range(len(work))]; fin[i] = True; changed = True
    dead = [f"P{i}" for i, f in enumerate(fin) if not f]
    return {"deadlocked": bool(dead), "deadlocked_processes": dead, "is_simulation": True}


def wait_for_cycle(edges: list[list[str]]) -> dict:
    g: dict[str, list[str]] = {}
    for a, b in edges:
        g.setdefault(a, []).append(b); g.setdefault(b, [])
    color, parent = {}, {}

    def dfs(u):
        color[u] = 1
        for v in g[u]:
            if color.get(v, 0) == 0:
                parent[v] = u
                c = dfs(v)
                if c:
                    return c
            elif color[v] == 1:
                cyc, x = [v], u
                while x != v:
                    cyc.append(x); x = parent[x]
                return cyc[::-1]
        color[u] = 2
        return None
    for u in list(g):
        if color.get(u, 0) == 0:
            c = dfs(u)
            if c:
                return {"cycle": c, "deadlock": True, "is_simulation": True}
    return {"cycle": [], "deadlock": False, "is_simulation": True}
