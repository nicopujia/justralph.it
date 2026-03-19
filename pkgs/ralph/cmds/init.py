"""``ralph init`` — scaffold the .ralph/ directory."""

import logging

from ..config import Config
from ..lib.init import init_ralph_dir

logger = logging.getLogger(__name__)


def run(cfg: Config) -> None:
    """Scaffold the .ralph/ directory with default files.

    Creates the base directory, logs directory, default hooks file,
    and .gitignore. Safe to re-run — existing files are not overwritten.
    """
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="[%(levelname)s] %(message)s",
    )
    init_ralph_dir(cfg)
    logger.info("Initialized %s", cfg.base_dir)
