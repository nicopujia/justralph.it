"""Single source of truth for Ralph's base configuration and defaults.

Every configurable value is defined exactly once. The CLI layer reads
dataclass fields + metadata to build ``argparse`` flags automatically.

Field metadata keys
-------------------
* ``help``    - description shown in ``--help``
* ``cli``     - if explicitly ``False``, the field is hidden from the CLI
* ``env``     - environment-variable name that overrides the default
* ``choices`` - passed through to argparse
"""

import os
from dataclasses import dataclass, field, fields
from pathlib import Path

# Ralph identity
AGENT_NAME = "ralph"

# Branch and worktree names
MAIN_BRANCH = "main"
PROD_WORKTREE = "prod"
DEV_WORKTREE = "dev"

# Directory and file names
RALPH_DIR_NAME = ".ralph"
HOOKS_FILENAME = "hooks.py"
HOOKS_CLASS_NAME = "CustomHooks"
HOOKS_MODULE_NAME = "_ralph_hooks"
BRANCH_PREFIX = "ralph/"

# Tag prefixes
PRE_ITER_TAG_PREFIX = "pre-iter"
DONE_TAG_PREFIX = "done"

# Default project root (current working directory)
PROJECT_ROOT = Path.cwd()
RALPH_DIR = PROJECT_ROOT / PROD_WORKTREE / RALPH_DIR_NAME
LOGS_DIR = RALPH_DIR / "logs"


@dataclass
class Config:
    """Global configuration shared by every command."""

    base_dir: Path = field(
        default=PROJECT_ROOT,
        metadata={"help": "Project root directory"},
    )
    log_level: str = field(
        default="INFO",
        metadata={
            "help": "Log level",
            "env": "LOG_LEVEL",
            "choices": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        },
    )


def get_fields(cfg_cls: type = Config, *, exclude: type | None = None):
    """Yield ``(field_obj, cli_flag, default_value)`` for *cfg_cls*.

    Args:
        cfg_cls: The config dataclass to inspect.
        exclude: A parent config class whose fields should be skipped.
    """
    excluded = {f.name for f in fields(exclude)} if exclude else set()

    for f in fields(cfg_cls):
        if f.metadata.get("cli") is False or f.name in excluded:
            continue
        flag = f"--{f.name.replace('_', '-')}"
        env_name = f.metadata.get("env")
        default = os.environ.get(env_name, f.default) if env_name else f.default
        yield f, flag, default
