"""Memory-management SIMULATOR (paging, TLB, replacement, partitions). Does not touch real host memory."""


def translate(addresses: list[int], page_size: int, page_table: dict[int, int], tlb_size: int = 0) -> dict:
    if page_size <= 0 or page_size & (page_size - 1):
        raise ValueError("page_size must be a positive power of two")
    tlb, steps, hits = [], [], 0
    for va in addresses:
        if va < 0:
            raise ValueError("addresses must be >= 0")
        page, off = divmod(va, page_size)
        hit = page in tlb
        if hit:
            hits += 1
            frame = page_table[page]
        elif page in page_table:
            frame = page_table[page]
            if tlb_size:
                tlb.append(page)
                if len(tlb) > tlb_size:
                    tlb.pop(0)
        else:
            steps.append({"virtual": va, "page": page, "offset": off, "fault": True, "tlb_hit": False}); continue
        steps.append({"virtual": va, "page": page, "offset": off, "frame": frame, "physical": frame * page_size + off,
                      "tlb_hit": hit, "fault": False})
    return {"steps": steps, "tlb_hits": hits, "tlb_lookups": len(addresses), "is_simulation": True}


def replace(algo: str, refs: list[int], frames: int) -> dict:
    if frames <= 0:
        raise ValueError("frames must be > 0")
    mem, order, steps, faults = [], [], [], 0   # `order` = FIFO arrival / LRU recency (front = victim)
    for i, r in enumerate(refs):
        fault, victim = r not in mem, None
        if fault:
            faults += 1
            if len(mem) == frames:
                if algo in ("fifo", "lru"):
                    victim = order.pop(0)
                elif algo == "optimal":
                    def nxt(p):
                        try:
                            return refs.index(p, i + 1)
                        except ValueError:
                            return float("inf")
                    victim = max(mem, key=nxt)
                    order.remove(victim)
                else:
                    raise ValueError("algorithm must be fifo, lru or optimal")
                mem.remove(victim)
            mem.append(r); order.append(r)
        elif algo == "lru":
            order.remove(r); order.append(r)
        steps.append({"ref": r, "frames": list(mem), "fault": fault, "evicted": victim})
    return {"algorithm": algo, "faults": faults, "hits": len(refs) - faults, "fault_rate": round(faults / len(refs), 3) if refs else 0,
            "steps": steps, "is_simulation": True,
            "note": "Optimal needs future knowledge: it is a theoretical lower bound, not implementable in a real OS."}


def partition(strategy: str, blocks: list[int], procs: list[int]) -> dict:
    free, out = list(blocks), []
    for i, p in enumerate(procs):
        fits = [(j, b) for j, b in enumerate(free) if b >= p]
        if not fits:
            out.append({"process": i, "size": p, "block": None}); continue
        j, _ = {"first": fits[0], "best": min(fits, key=lambda x: x[1]), "worst": max(fits, key=lambda x: x[1])}[strategy]
        out.append({"process": i, "size": p, "block": j, "internal_fragmentation": free[j] - p}); free[j] -= p
    return {"strategy": strategy, "allocations": out, "remaining_free": free, "is_simulation": True}
