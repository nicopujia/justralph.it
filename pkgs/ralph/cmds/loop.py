"""Run the main agent loop."""

import argparse
import logging
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import bd
import psutil

from ..config import BASE_DIR, LOGS_DIR, Config
from ..core.agent import Agent
from ..core.hooks import load_hooks
from ..core.state import State
from ..utils.git import reset_git_state
from . import Command

logger = logging.getLogger(__name__)


@dataclass
class LoopConfig(Config):
    """Configuration for the loop command."""

    log_file: Path = field(
        default=LOGS_DIR / "main.log",
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
    model: str = field(
        default="opencode/kimi-k2.5",
        metadata={"help": "Model to use. Read more: https://opencode.ai/docs/models"},
    )
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


class Loop(Command):
    help = "Run the main agent loop"
    config = LoopConfig
    cfg: LoopConfig

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--once",
            dest="max_iters",
            action="store_const",
            const=1,
            help="Run a single iteration (alias for --max-iters 1)",
        )

    def run(self) -> None:
        """Load hooks and enter the restart-aware iteration loop.

        Exits with code 1 if .ralph/ has not been initialized.
        """
        cfg = self.cfg

        if not cfg.base_dir.is_dir():
            print(
                f"Error: {cfg.base_dir} does not exist. Run 'ralph init' first.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        # Add a file handler on top of the root logging configured by main.py
        file_handler = logging.FileHandler(filename=cfg.log_file)
        file_handler.setFormatter(logging.getLogger().handlers[0].formatter)
        logging.getLogger().addHandler(file_handler)

        self._loop_state = State(cfg.state_file)
        self._hooks = load_hooks(cfg)

        while True:
            restart = self._iterate()
            if not restart:
                break
            logger.info("Restarting loop")

    def _iterate(self) -> bool:
        """Run iterations until stopped, restarted, or max iterations reached.

        Each iteration:
        1. Check for stop/restart signal files
        2. Verify machine resources (CPU, RAM, disk) are below threshold
        3. Poll for a ready issue (or wait for one)
        4. Create an Agent and claim the issue
        5. Reset git state and run the agent
        6. Handle completion (done/blocked/help) or failure
        7. Retry on failure with exponential backoff

        Returns True if a restart was requested, False if stopping normally.
        """
        cfg = self.cfg
        hooks = self._hooks
        loop_state = self._loop_state
        log_fmt = logging.getLogger().handlers[0].formatter

        i = loop_state.check_crash_recovery()

        logger.info("Calling pre-loop hook")
        hooks.pre_loop(cfg)

        if cfg.max_iters:
            logger.info("Starting the loop")
        else:
            logger.warning("Skipping entire loop: max_iters is 0")
        consecutive_failures = 0
        restart = False

        while True and cfg.max_iters:
            if cfg.stop_file.exists():
                reason = cfg.stop_file.read_text() or "found empty stop file"
                cfg.stop_file.unlink()
                logging.warning("Stopping loop: %s", reason)
                break

            if cfg.restart_file.exists():
                reason = cfg.restart_file.read_text() or "found empty restart file"
                cfg.restart_file.unlink()
                logger.info("Restart requested: %s", reason)
                restart = True
                break

            logger.info("Checking machine resources")
            cpu = round(psutil.cpu_percent(), 2)
            ram = round(psutil.virtual_memory().percent, 2)
            total_disk, used_disk, _ = shutil.disk_usage("/")
            disk = round(used_disk / total_disk * 100, 2)
            logger.info("CPU: %s%% | RAM: %s%% | Disk: %s%%", cpu, ram, disk)
            if (
                disk > cfg.vm_res_threshold
                or ram > cfg.vm_res_threshold
                or cpu > cfg.vm_res_threshold
            ):
                logger.warning(
                    "Stopping loop: machine resources usage over %s%% threshold",
                    cfg.vm_res_threshold,
                )
                break
            else:
                logger.info("Machine resources usage is OK")

            logger.info("Getting next ready issue")
            issue = bd.get_next_ready_issue()

            if not issue:
                logger.info("No ready issues currently. Waiting for new ones")
                try:
                    issue = bd.wait_for_next_ready_issue(
                        cfg.poll_interval,
                        stop_file=cfg.stop_file,
                        restart_file=cfg.restart_file,
                    )
                except bd.StopRequested as e:
                    logger.warning("Stopping loop while waiting for issues: %s", e)
                    break
                except bd.RestartRequested as e:
                    logger.info("Restart requested while waiting for issues: %s", e)
                    restart = True
                    break

            logger.info("Retrieved issue: %r", issue)

            logger.info("Getting extra args & kwargs")
            extra_args, extra_kwargs = hooks.extra_args_kwargs(cfg, issue)

            logger.info(
                "Creating instance with extra args %s and kwargs %s",
                extra_args,
                extra_kwargs,
            )
            ralph = Agent(
                issue,
                cfg.model,
                i,
                *extra_args,
                **extra_kwargs,
            )

            ralph.claim_issue()

            logger.info("Preparing git state for issue %s", issue.id)
            reset_git_state(issue.id)

            iter_log_file = cfg.logs_dir / f"iteration_{i}.log"
            iter_handler = logging.FileHandler(filename=iter_log_file)
            iter_handler.setFormatter(log_fmt)
            logging.getLogger().addHandler(iter_handler)

            logger.info("Calling pre-iteration hook")
            hooks.pre_iter(cfg, issue, i)

            loop_state.save(issue.id, i)

            iter_error: Exception | None = None
            try:
                logger.info("Starting Ralph")
                for stdout in ralph.run(timeout=cfg.subprocess_timeout):
                    logger.info("[Ralph] %s", stdout.rstrip())
                logger.info("Ralph concluded working: %s", ralph.status)

                match ralph.status:
                    case Agent.Status.DONE:
                        logger.info("Marking issue %s as done", issue.id)
                        bd.close_issue(issue.id)
                    case Agent.Status.BLOCKED:
                        logger.info("Issue %s has blockers", issue.id)
                        loop_state.cleanup_failed_iteration(status="blocked")
                    case Agent.Status.HELP:
                        logger.info(
                            "Issue %s needs human help (blocked by human-help issue)",
                            issue.id,
                        )
                        loop_state.cleanup_failed_iteration(status="blocked")
                    case _:
                        logger.warning(
                            "Unexpected status %s for issue %s; treating as failure",
                            ralph.status,
                            issue.id,
                        )
                        loop_state.cleanup_failed_iteration()
                        raise ValueError(f"Unexpected Ralph status: {ralph.status}")

                consecutive_failures = 0
            except Exception as exc:
                iter_error = exc
                consecutive_failures += 1
                logger.exception(
                    "Failed unexpectedly (consecutive failures: %s)",
                    consecutive_failures,
                )
                loop_state.cleanup_failed_iteration()
                if cfg.max_retries >= 0 and consecutive_failures > cfg.max_retries:
                    cfg.stop_file.write_text(
                        f"exceeded max retries ({cfg.max_retries}) "
                        f"after {consecutive_failures} consecutive failures"
                    )
                    logger.error("Max retries exceeded; will stop on next iteration")
                else:
                    backoff = min(2**consecutive_failures, 300)
                    logger.info("Backing off for %ss before retrying", backoff)
                    time.sleep(backoff)
            finally:
                logger.info("Calling post-iteration hook")
                hooks.post_iter(cfg, issue, i, ralph.status, iter_error)

                i += 1
                loop_state.clear()
                iter_handler.close()
                logging.getLogger().removeHandler(iter_handler)

                if cfg.max_iters >= 0 and i >= cfg.max_iters:
                    logger.warning(
                        "Stopping loop: reached max iterations (%s)",
                        cfg.max_iters,
                    )
                    break

        logger.info("Finished loop. Calling post-loop hook")
        hooks.post_loop(cfg, i)

        return restart
