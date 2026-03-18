import argparse
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path.cwd() / ".ralph"
LOGS_DIR = BASE_DIR / "logs"
STATE_FILE = BASE_DIR / "state.json"
MAIN_LOG_FILE = LOGS_DIR / "main.log"
STOP_FILE = BASE_DIR / "stop.ralph"
RESTART_FILE = BASE_DIR / "restart.ralph"

MODEL = "opencode/kimi-k2.5"

VM_RES_THRESHOLD = 95.0  # %
POLL_INTERVAL = 30.0  # seconds
SUBPROCESS_TIMEOUT = 600.0  # 10 minutes
MAX_ITERS = -1  # infinite
MAX_RETRIES = -1  # infinite


@dataclass
class Config:
    model: str = MODEL
    stop_file: Path = STOP_FILE
    restart_file: Path = RESTART_FILE
    state_file: Path = STATE_FILE
    log_file: Path = MAIN_LOG_FILE
    logs_dir: Path = LOGS_DIR
    vm_res_threshold: float = VM_RES_THRESHOLD
    max_iters: int = MAX_ITERS
    base_dir: Path = BASE_DIR
    poll_interval: float = POLL_INTERVAL
    subprocess_timeout: float = SUBPROCESS_TIMEOUT
    max_retries: int = MAX_RETRIES


def get_config() -> Config:
    parser = argparse.ArgumentParser(description="Ralph")
    parser.add_argument(
        "--model",
        type=str,
        default=MODEL,
        help=f"Model to use (default: {MODEL}). Read more: https://opencode.ai/docs/models",
    )
    parser.add_argument(
        "--stop-file",
        type=Path,
        default=STOP_FILE,
        help=f"Path to stop file (default: {STOP_FILE})",
    )
    parser.add_argument(
        "--restart-file",
        type=Path,
        default=RESTART_FILE,
        help=f"Path to restart file (default: {RESTART_FILE})",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=STATE_FILE,
        help=f"Path to state file for crash recovery (default: {STATE_FILE})",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=MAIN_LOG_FILE,
        help=f"Path to log file (default: {MAIN_LOG_FILE})",
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=LOGS_DIR,
        help=f"Path to logs directory (default: {LOGS_DIR})",
    )
    parser.add_argument(
        "--vm-res-threshold",
        type=float,
        default=VM_RES_THRESHOLD,
        help=f"VM resource threshold in percent (default: {VM_RES_THRESHOLD})",
    )
    parser.add_argument(
        "--max-iters",
        type=int,
        default=MAX_ITERS,
        help=f"Maximum iterations (-1 for no limit, default: {MAX_ITERS})",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=BASE_DIR,
        help=f"Base directory for Ralph runtime files (default: {BASE_DIR})",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=POLL_INTERVAL,
        help=f"Poll interval in seconds for checking new issues (default: {POLL_INTERVAL})",
    )
    parser.add_argument(
        "--subprocess-timeout",
        type=float,
        default=SUBPROCESS_TIMEOUT,
        help=f"Timeout for OpenCode subprocess in seconds (default: {SUBPROCESS_TIMEOUT})",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=MAX_RETRIES,
        help=f"Max retries on failure (-1 for no limit, default: {MAX_RETRIES})",
    )
    namespace = parser.parse_args()
    return Config(**vars(namespace))
