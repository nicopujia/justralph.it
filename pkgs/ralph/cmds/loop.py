"""``ralph loop`` — run the main agent loop."""

import sys

from ..config import Config
from ..lib.loop import run_loop


def run(cfg: Config) -> None:
    """Run the main Ralph loop.

    Raises ``SystemExit(1)`` if .ralph/ has not been initialized.
    """
    if not cfg.base_dir.is_dir():
        print(
            f"Error: {cfg.base_dir} does not exist. Run 'ralph init' first.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    run_loop(cfg)
