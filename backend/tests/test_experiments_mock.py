import pytest
from unittest.mock import MagicMock, patch
from app.experiments.engine import ExperimentEngine, EXPERIMENTS
from app.core.models import ContainerCreate, Limits, Namespaces, WorkloadSpec
from app.database.db import Database

class MockManager:
    def create(self, req):
        return {"id": "mock-id", "path": "/sys/fs/cgroup/mock"}
    def start(self, cid, spec):
        pass
    def wait(self, cid, timeout):
        pass
    def workloads(self, cid):
        return [{"duration_s": 1.0, "exit_code": 0, "termination_reason": "completed",
                 "cpu_usec": 1000, "nr_throttled": 0, "throttled_usec": 0,
                 "peak_memory_bytes": 1024, "oom_kills": 0,
                 "output_tail": '{"wall_sec": 1.1}'}]
    def remove(self, cid):
        pass

@pytest.fixture
def engine():
    db = MagicMock(spec=Database)
    mgr = MockManager()
    return ExperimentEngine(db, mgr)

def test_experiment_e_parallel_logic(engine):
    with patch.object(engine.mgr, 'start') as mock_start, \
         patch.object(engine.mgr, 'wait') as mock_wait:

        engine._run("test-id", "competing-workloads", runs=1)

        assert mock_start.call_count >= 2
        assert mock_wait.call_count >= 2

def test_experiment_e_one_fails(engine):
    class FailingManager(MockManager):
        def __init__(self):
            self.start_calls = 0

        def start(self, cid, spec):
            self.start_calls += 1
            if self.start_calls == 3:
                raise Exception("Start failed")
            super().start(cid, spec)

    engine.mgr = FailingManager()
    engine._run("test-id", "competing-workloads", runs=1)

    calls = engine.db.execute.call_args_list
    # The results are saved in the last call
    sql, params = calls[-1][0]
    results_json_str = params[1]
    import json
    results = json.loads(results_json_str)

    # Check if any entry in raw has the error
    found = any("Parallel run failed" in str(r.get("error", "")) for r in results.get("raw", []))
    assert found, f"Expected 'Parallel run failed' in raw results: {results.get('raw')}"

def test_experiment_f_overhead_calc(engine):
    raw = [
        {"config": "minimal", "duration_s": 1.0, "workload_output": {"wall_sec": 1.2},
         "cpu_usec": 0, "nr_throttled": 0, "throttled_usec": 0, "peak_memory_bytes": 0,
         "oom_kills": 0, "termination_reason": "completed"}
    ]
    analysis = engine._analyse("lifecycle-overhead", raw)
    note = analysis["interpretation"][0]
    assert "estimated setup overhead: 0.2s" in note
    assert "Note: This is an estimate" in note

def test_experiment_g_monitoring_errors(engine):
    raw = [{"config": "high-freq-monitoring", "run": 0, "duration_s": 1.0,
            "cpu_usec": 0, "nr_throttled": 0, "throttled_usec": 0, "peak_memory_bytes": 0,
            "oom_kills": 0, "termination_reason": "completed",
            "workload_output": {"wall_sec": 1.1},
            "mon_samples": 50, "mon_errors": ["OSError: [Errno 2] No such file"]}]

    analysis = engine._analyse("monitoring-cost", raw)
    assert analysis["raw"][0]["mon_errors"] == ["OSError: [Errno 2] No such file"]

def test_cleanup_failure_visibility(engine):
    class CleanupFailManager(MockManager):
        def remove(self, cid):
            raise Exception("Cleanup failed")

    engine.mgr = CleanupFailManager()

    # Test Experiments A-D (via _one)
    engine._run("test-id-a", "pid-isolation", runs=1)
    calls_a = engine.db.execute.call_args_list
    results_a = calls_a[-1][0][1] if len(calls_a[-1][0]) > 1 else ""
    # Note: Since I don't know the exact params index, I'll search the whole param tuple
    found_a = any("Cleanup failed" in str(p) for p in calls_a[-1][0])

    # Test E (parallel)
    engine.mgr = CleanupFailManager()
    engine._run("test-id-e", "competing-workloads", runs=1)
    calls_e = engine.db.execute.call_args_list
    found_e = any("Cleanup failed" in str(p) for p in calls_e[-1][0])

    assert found_a, "Cleanup failure not recorded for Experiment A-D"
    assert found_e, "Cleanup failure not recorded for Experiment E"
