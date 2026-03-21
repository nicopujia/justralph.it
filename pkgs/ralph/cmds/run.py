"""Run the Ralph Loop: process tasks via OpenCode."""

import logging
import signal
import sys

from ..config import RALPHY_DIR_NAME
from ..core.events import EventBus
from ..core.hooks import load_hooks
from ..core.ralphy_runner import RalphyRunner, RunnerConfig
from . import Command

logger = logging.getLogger(__name__)


class Run(Command):
    help = "Run the Ralph Loop (processes tasks via OpenCode)"
    config = RunnerConfig
    cfg: RunnerConfig
    event_bus: "EventBus | None" = None

    def run(self) -> None:
        """Validate setup, then launch the RalphyRunner."""
        ralphy_dir = self.cfg.project_dir / RALPHY_DIR_NAME
        if not ralphy_dir.is_dir():
            msg = f"{ralphy_dir} does not exist. Run 'ralph init' first."
            print(f"Error: {msg}", file=sys.stderr)
            raise SystemExit(1)

        tasks_file = self.cfg.tasks_file
        if not tasks_file.exists():
            msg = f"{tasks_file} does not exist. Create tasks first: ralph task create ..."
            print(f"Error: {msg}", file=sys.stderr)
            raise SystemExit(1)

        # Set up logging to file
        log_dir = ralphy_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "main.log")
        file_handler.setFormatter(logging.getLogger().handlers[0].formatter)
        logging.getLogger().addHandler(file_handler)

        # Load hooks (optional -- don't fail if missing)
        hooks = None
        try:
            hooks = load_hooks(self.cfg)
        except FileNotFoundError:
            logger.info("No hooks file found, running without hooks")

        # Signal handling: write stop file on SIGINT/SIGTERM
        def _signal_handler(signum, _frame):
            sig_name = signal.Signals(signum).name
            logger.warning("Received %s, writing stop file", sig_name)
            self.cfg.stop_file.write_text(f"received {sig_name}")

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        runner = RalphyRunner(
            config=self.cfg,
            hooks=hooks,
            bus=self.event_bus,
        )
        runner.run()
