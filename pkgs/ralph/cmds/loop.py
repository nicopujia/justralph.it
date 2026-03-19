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
from bd import Issue

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
        """Verify initialization, set up state, and loop until stopped."""
        if not self.cfg.base_dir.is_dir():
            print(
                f"Error: {self.cfg.base_dir} does not exist. Run 'ralph init' first.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        file_handler = logging.FileHandler(filename=self.cfg.log_file)
        file_handler.setFormatter(logging.getLogger().handlers[0].formatter)
        logging.getLogger().addHandler(file_handler)

        self._state = State(self.cfg.state_file)
        self._hooks = load_hooks(self.cfg)
        self._consecutive_failures = 0

        while True:
            restart = self._iterate()
            if not restart:
                break
            logger.info("Restarting loop")

    # -- main loop ---------------------------------------------------------

    def _iterate(self) -> bool:
        """Run iterations until stopped, restarted, or max iterations reached.

        Returns True if a restart was requested, False otherwise.
        """
        i = self._state.check_crash_recovery()

        self._hooks.pre_loop(self.cfg)

        if not self.cfg.max_iters:
            logger.warning("Skipping entire loop: max_iters is 0")

        while self.cfg.max_iters:
            try:
                self._check_signals()
                self._check_resources()
                issue = self._next_issue()
                agent = self._create_agent(issue, i)
                self._process_issue(agent, issue, i)
                self._consecutive_failures = 0
            except bd.StopRequested:
                break
            except bd.RestartRequested:
                self._hooks.post_loop(self.cfg, i)
                return True
            except Exception as exc:
                self._handle_failure(exc)
            finally:
                i += 1
                self._state.clear()
                if self.cfg.max_iters >= 0 and i >= self.cfg.max_iters:
                    logger.warning(
                        "Stopping loop: reached max iterations (%s)",
                        self.cfg.max_iters,
                    )
                    break

        self._hooks.post_loop(self.cfg, i)
        return False

    # -- signal and resource checks ----------------------------------------

    def _check_signals(self) -> None:
        """Read stop/restart signal files and raise accordingly."""
        if self.cfg.stop_file.exists():
            reason = self.cfg.stop_file.read_text() or "found empty stop file"
            self.cfg.stop_file.unlink()
            logger.warning("Stopping loop: %s", reason)
            raise bd.StopRequested(reason)

        if self.cfg.restart_file.exists():
            reason = self.cfg.restart_file.read_text() or "found empty restart file"
            self.cfg.restart_file.unlink()
            logger.info("Restart requested: %s", reason)
            raise bd.RestartRequested(reason)

    def _check_resources(self) -> None:
        """Stop if CPU, RAM, or disk usage exceeds the threshold."""
        cpu = round(psutil.cpu_percent(), 2)
        ram = round(psutil.virtual_memory().percent, 2)
        total_disk, used_disk, _ = shutil.disk_usage("/")
        disk = round(used_disk / total_disk * 100, 2)
        logger.info("CPU: %s%% | RAM: %s%% | Disk: %s%%", cpu, ram, disk)

        threshold = self.cfg.vm_res_threshold
        if cpu > threshold or ram > threshold or disk > threshold:
            logger.warning(
                "Stopping loop: resource usage over %s%% threshold", threshold
            )
            raise bd.StopRequested("resource usage over threshold")

    # -- issue acquisition -------------------------------------------------

    def _next_issue(self) -> Issue:
        """Return the next ready issue, blocking if none are available."""
        issue = bd.get_next_ready_issue()
        if issue:
            logger.info("Retrieved issue: %r", issue)
            return issue

        logger.info("No ready issues. Waiting...")
        try:
            return bd.wait_for_next_ready_issue(
                self.cfg.poll_interval,
                stop_file=self.cfg.stop_file,
                restart_file=self.cfg.restart_file,
            )
        except bd.StopRequested:
            logger.warning("Stopping while waiting for issues")
            raise
        except bd.RestartRequested:
            logger.info("Restart requested while waiting for issues")
            raise

    # -- agent lifecycle ---------------------------------------------------

    def _create_agent(self, issue: Issue, iteration: int) -> Agent:
        """Build an Agent, claim the issue, and prepare git state."""
        extra_args, extra_kwargs = self._hooks.extra_args_kwargs(self.cfg, issue)
        agent = Agent(issue, self.cfg.model, iteration, *extra_args, **extra_kwargs)
        agent.claim_issue()
        reset_git_state(issue.id)
        return agent

    def _process_issue(self, agent: Agent, issue: Issue, iteration: int) -> None:
        """Run the agent and handle its outcome."""
        iter_handler = self._add_iteration_log(iteration)
        self._hooks.pre_iter(self.cfg, issue, iteration)
        self._state.save(issue.id, iteration)

        iter_error: Exception | None = None
        try:
            self._run_agent(agent)
            self._handle_status(agent, issue)
        except Exception as exc:
            iter_error = exc
            raise
        finally:
            self._hooks.post_iter(self.cfg, issue, iteration, agent.status, iter_error)
            self._remove_iteration_log(iter_handler)

    def _run_agent(self, agent: Agent) -> None:
        """Stream agent output to the logger."""
        logger.info("Starting agent")
        for line in agent.run(timeout=self.cfg.subprocess_timeout):
            logger.info("[agent] %s", line.rstrip())
        logger.info("Agent finished: %s", agent.status)

    def _handle_status(self, agent: Agent, issue: Issue) -> None:
        """Act on the agent's final status."""
        match agent.status:
            case Agent.Status.DONE:
                logger.info("Marking issue %s as done", issue.id)
                bd.close_issue(issue.id)
            case Agent.Status.BLOCKED | Agent.Status.HELP:
                logger.info("Issue %s is blocked", issue.id)
                self._state.cleanup_failed_iteration(status="blocked")
            case _:
                logger.warning(
                    "Unexpected status %s for issue %s",
                    agent.status,
                    issue.id,
                )
                self._state.cleanup_failed_iteration()
                raise ValueError(f"Unexpected agent status: {agent.status}")

    # -- failure handling --------------------------------------------------

    def _handle_failure(self, exc: Exception) -> None:
        """Log the failure, clean up, and apply backoff or stop."""
        self._consecutive_failures += 1
        logger.exception(
            "Failed unexpectedly (consecutive failures: %s)",
            self._consecutive_failures,
        )
        self._state.cleanup_failed_iteration()

        if (
            self.cfg.max_retries >= 0
            and self._consecutive_failures > self.cfg.max_retries
        ):
            self.cfg.stop_file.write_text(
                f"exceeded max retries ({self.cfg.max_retries}) "
                f"after {self._consecutive_failures} consecutive failures"
            )
            logger.error("Max retries exceeded; will stop on next iteration")
        else:
            backoff = min(2**self._consecutive_failures, 300)
            logger.info("Backing off for %ss before retrying", backoff)
            time.sleep(backoff)

    # -- logging helpers ---------------------------------------------------

    def _add_iteration_log(self, iteration: int) -> logging.FileHandler:
        """Attach a per-iteration log file and return the handler."""
        path = self.cfg.logs_dir / f"iteration_{iteration}.log"
        handler = logging.FileHandler(filename=path)
        handler.setFormatter(logging.getLogger().handlers[0].formatter)
        logging.getLogger().addHandler(handler)
        return handler

    @staticmethod
    def _remove_iteration_log(handler: logging.FileHandler) -> None:
        """Close and detach a per-iteration log handler."""
        handler.close()
        logging.getLogger().removeHandler(handler)
