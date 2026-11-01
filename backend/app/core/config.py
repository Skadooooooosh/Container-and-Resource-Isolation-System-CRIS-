"""Paths and tunables. Override with environment variables."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.environ.get("CRIS_DATA", ROOT / "data"))
NATIVE_DIR = Path(os.environ.get("CRIS_NATIVE", ROOT / "native" / "build"))
CRIS_RUN = NATIVE_DIR / "cris_run"
CRIS_WORKLOAD = NATIVE_DIR / "cris_workload"
DB_PATH = DATA_DIR / "cris.sqlite3"
LOG_DIR = DATA_DIR / "logs"
SAMPLE_INTERVAL_S = float(os.environ.get("CRIS_SAMPLE_INTERVAL", "0.5"))
MAX_LOG_BYTES = 1_000_000          # a workload exceeding this is killed (output-size limit)
CGROUP_ROOT = Path("/sys/fs/cgroup")
CPU_PERIOD_US = 100_000
START_TIMEOUT_S = 5.0


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
