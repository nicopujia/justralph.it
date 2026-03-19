"""Single source of truth for Ralph's configuration and defaults.

Every configurable value is defined here exactly once as a field on the
:class:`Config` dataclass.  The CLI layer (``ralph.main``) reads field
metadata to build ``argparse`` flags automatically — no duplication needed.

Field metadata keys
-------------------
* ``help``  – description shown in ``--help`` (required for CLI-exposed fields)
* ``cli``   – if explicitly ``False``, the field is hidden from the CLI
* ``env``   – environment-variable name that overrides the default
* ``choices`` – passed through to argparse
"""

import os
from dataclasses import dataclass, field, fields
from pathlib import Path

# ── Base paths (derived, not directly configurable) ──────────────────────
BASE_DIR = Path.cwd() / ".ralph"
LOGS_DIR = BASE_DIR / "logs"


@dataclass
class Config:
    """Runtime configuration for Ralph.

    Every field carries its own default and ``metadata["help"]`` docstring so
    that ``ralph <cmd> --help`` stays in sync automatically.
    """

    # ── Paths ────────────────────────────────────────────────────────────
    base_dir: Path = field(
        default=BASE_DIR,
        metadata={"help": "Base directory for Ralph runtime files"},
    )
    log_file: Path = field(
        default=BASE_DIR / "logs" / "main.log",
        metadata={"help": "Path to log file"},
    )
    logs_dir: Path = field(
        default=LOGS_DIR,
        metadata={"help": "Path to logs directory"},
    )
    state_file: Path = field(
        default=BASE_DIR / "state.json",
        metadata={"help": "Path to state file for crash recovery"},
    )
    stop_file: Path = field(
        default=BASE_DIR / "stop.ralph",
        metadata={"help": "Path to stop file"},
    )
    restart_file: Path = field(
        default=BASE_DIR / "restart.ralph",
        metadata={"help": "Path to restart file"},
    )

    # ── Strings ──────────────────────────────────────────────────────────
    model: str = field(
        default="opencode/kimi-k2.5",
        metadata={
            "help": ("Model to use. Read more: https://opencode.ai/docs/models"),
        },
    )
    log_level: str = field(
        default="INFO",
        metadata={
            "help": "Log level",
            "env": "LOG_LEVEL",
            "choices": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        },
    )

    # ── Numbers ──────────────────────────────────────────────────────────
    vm_res_threshold: float = field(
        default=95.0,
        metadata={"help": "VM resource threshold in percent"},
    )
    poll_interval: float = field(
        default=30.0,
        metadata={"help": "Poll interval in seconds for checking new issues"},
    )
    subprocess_timeout: float = field(
        default=600.0,
        metadata={"help": "Timeout for OpenCode subprocess in seconds"},
    )
    max_iters: int = field(
        default=-1,
        metadata={"help": "Maximum iterations (-1 for no limit)"},
    )
    max_retries: int = field(
        default=-1,
        metadata={"help": "Max retries on failure (-1 for no limit)"},
    )


def get_fields():
    """Yield ``(field_obj, cli_flag, default_value)`` for every CLI-visible field."""
    for f in fields(Config):
        if f.metadata.get("cli") is False:
            continue
        flag = f"--{f.name.replace('_', '-')}"
        # Resolve env-var override
        env_name = f.metadata.get("env")
        default = os.environ.get(env_name, f.default) if env_name else f.default
        yield f, flag, default
