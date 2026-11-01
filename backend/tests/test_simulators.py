import pytest
from app.simulators import deadlock, disk, memory, scheduling, sync

P = [{"pid": "P1", "arrival": 0, "burst": 5}, {"pid": "P2", "arrival": 1, "burst": 3},
     {"pid": "P3", "arrival": 2, "burst": 8}, {"pid": "P4", "arrival": 3, "burst": 6}]


def comp(res): return {r["pid"]: r["completion"] for r in res["table"]}


def test_fcfs():
    r = scheduling.simulate("fcfs", P)
    assert comp(r) == {"P1": 5, "P2": 8, "P3": 16, "P4": 22} and r["avg_waiting"] == 5.75


def test_sjf():
    r = scheduling.simulate("sjf", P)
    assert comp(r) == {"P1": 5, "P2": 8, "P3": 22, "P4": 14} and r["avg_waiting"] == 5.25


def test_srtf():
    r = scheduling.simulate("srtf", P)
    assert comp(r) == {"P1": 8, "P2": 4, "P3": 22, "P4": 14} and r["avg_waiting"] == 5.0


def test_rr():
    r = scheduling.simulate("rr", P, quantum=2)
    assert comp(r) == {"P1": 14, "P2": 11, "P3": 22, "P4": 20} and r["avg_waiting"] == 9.75


def test_priority_and_idle_gap():
    r = scheduling.simulate("priority", [{"pid": "A", "arrival": 5, "burst": 2, "priority": 1}])
    assert r["gantt"][0]["pid"] == "idle" and comp(r) == {"A": 7}


def test_mlfq_completes_all():
    r = scheduling.simulate("mlfq", P)
    assert set(comp(r)) == {"P1", "P2", "P3", "P4"}
    assert sum(g["end"] - g["start"] for g in r["gantt"] if g["pid"] != "idle") == 22


def test_sched_validation():
    with pytest.raises(ValueError): scheduling.simulate("fcfs", [{"pid": "x", "burst": 0}])
    with pytest.raises(ValueError): scheduling.simulate("nope", P)


REFS = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]


@pytest.mark.parametrize("algo,faults", [("fifo", 15), ("lru", 12), ("optimal", 9)])
def test_page_replacement(algo, faults):
    assert memory.replace(algo, REFS, 3)["faults"] == faults


def test_translation_and_tlb():
    r = memory.translate([1030, 1030, 5000], 1024, {1: 7, 4: 2}, tlb_size=2)
    assert r["steps"][0]["physical"] == 7 * 1024 + 6 and r["steps"][1]["tlb_hit"] and r["tlb_hits"] == 1
    assert memory.translate([9999], 1024, {})["steps"][0]["fault"]
    with pytest.raises(ValueError): memory.translate([1], 1000, {})


def test_partition_fits():
    r = memory.partition("best", [100, 500, 200, 300, 600], [212, 417, 112, 426])
    assert [a["block"] for a in r["allocations"]] == [3, 1, 2, 4]


AV, MX = [3, 3, 2], [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]]
AL = [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]]


def test_banker_safe_and_request():
    s = deadlock.safety(AV, MX, AL)
    assert s["safe"] and sorted(s["safe_sequence"]) == ["P0", "P1", "P2", "P3", "P4"]
    assert deadlock.request(1, [1, 0, 2], AV, MX, AL)["granted"]
    AL2 = [r[:] for r in AL]; AL2[1] = [3, 0, 2]          # state after P1's request was granted
    assert not deadlock.request(0, [0, 2, 0], [2, 3, 0], MX, AL2)["granted"]   # textbook: unsafe


def test_detection_and_wfg():
    assert deadlock.detect([0, 0], [[1, 0], [0, 1]], [[0, 1], [1, 0]])["deadlocked_processes"] == ["P0", "P1"]
    assert not deadlock.detect([1, 1], [[1, 0], [0, 1]], [[0, 1], [1, 0]])["deadlocked"]
    assert deadlock.wait_for_cycle([["A", "B"], ["B", "C"], ["C", "A"]])["deadlock"]
    assert not deadlock.wait_for_cycle([["A", "B"], ["B", "C"]])["deadlock"]


Q = [98, 183, 37, 122, 14, 124, 65, 67]


@pytest.mark.parametrize("algo,kw,total", [("fcfs", {}, 640), ("sstf", {}, 236), ("scan", {"direction": "down"}, 236),
                                           ("look", {"direction": "down"}, 208), ("scan", {"direction": "up"}, 331),
                                           ("clook", {"direction": "up"}, 322), ("cscan", {"direction": "up"}, 382)])
def test_disk(algo, kw, total):
    assert disk.schedule(algo, Q, 53, 200, **kw)["total_movement"] == total


def test_race_and_sync():
    assert sync.race_interleaving("serial")["final"] == 6 and not sync.race_interleaving("serial")["race_detected"]
    assert sync.race_interleaving("interleaved")["race_detected"]
    pc = sync.producer_consumer(3, 200)
    assert pc["consumed"] == 200 and pc["in_order"] and pc["bound_respected"]
    assert sync.dining_philosophers(5, "naive")["deadlock"] and not sync.dining_philosophers(5, "ordered")["deadlock"]
