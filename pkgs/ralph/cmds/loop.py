"""Run the main agent loop."""

import argparse
import logging
import signal
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import bd
import psutil
from bd import Issue

from ..config import LOGS_DIR, PROD_WORKTREE, PROJECT_ROOT, RALPH_DIR, RALPH_DIR_NAME, Config
from ..core.agent import Agent, AgentStatus
from ..core.events import Event, EventBus, EventType
from ..core.exceptions import RestartRequested, StopRequested
from ..core.hooks import load_hooks
from ..core.state import State
from ..utils.git import reset_git_state
from . import Command

logger = logging.getLogger(__name__)

MAX_BACKOFF_SECONDS = 300


@dataclass
class LoopConfig(Config):
    """Configuration for the loop command.

    When ``base_dir`` differs from the default (cwd), ``__post_init__``
    recomputes path fields that still carry their cwd-based defaults so
    they point to the correct session directory.
    """

    log_file: Path = field(
        default=LOGS_DIR / "main.log",
        metadata={"help": "Path to log file"},
    )
    logs_dir: Path = field(
        default=LOGS_DIR,
        metadata={"help": "Path to logs directory"},
    )
    state_file: Path = field(
        default=RALPH_DIR / "state.json",
        metadata={"help": "Path to state file for crash recovery"},
    )
    stop_file: Path = field(
        default=RALPH_DIR / "stop.ralph",
        metadata={"help": "Path to stop file"},
    )
    restart_file: Path = field(
        default=RALPH_DIR / "restart.ralph",
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

    def __post_init__(self):
        """Recompute path defaults when base_dir is not the cwd."""
        if self.base_dir == PROJECT_ROOT:
            return
        ralph_dir = self.base_dir / PROD_WORKTREE / RALPH_DIR_NAME
        logs_dir = ralph_dir / "logs"
        # Only replace values that still match the cwd-based defaults
        if self.logs_dir == LOGS_DIR:
            self.logs_dir = logs_dir
        if self.log_file == LOGS_DIR / "main.log":
            self.log_file = logs_dir / "main.log"
        if self.state_file == RALPH_DIR / "state.json":
            self.state_file = ralph_dir / "state.json"
        if self.stop_file == RALPH_DIR / "stop.ralph":
            self.stop_file = ralph_dir / "stop.ralph"
        if self.restart_file == RALPH_DIR / "restart.ralph":
            self.restart_file = ralph_dir / "restart.ralph"


class Loop(Command):
    help = "Run the main agent loop"
    config = LoopConfig
    cfg: LoopConfig
    event_bus: "EventBus | None" = None  # set externally before run() for server usage

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
        ralph_dir = self.cfg.base_dir / PROD_WORKTREE / RALPH_DIR_NAME
        if not ralph_dir.is_dir():
            msg = f"{ralph_dir} does not exist. Run 'ralph init' first."
            print(f"Error: {msg}", file=sys.stderr)
            self._emit(EventType.LOOP_STOPPED, reason=msg, error=True)
            raise SystemExit(1)

        # Preflight: ensure required binaries are available
        for binary in ("opencode", "bd"):
            if not shutil.which(binary):
                msg = f"'{binary}' not found on PATH"
                print(f"Error: {msg}", file=sys.stderr)
                self._emit(EventType.LOOP_STOPPED, reason=msg, error=True)
                raise SystemExit(1)

        file_handler = logging.FileHandler(filename=self.cfg.log_file)
        file_handler.setFormatter(logging.getLogger().handlers[0].formatter)
        logging.getLogger().addHandler(file_handler)

        prod_dir = self.cfg.base_dir / PROD_WORKTREE
        self._state = State(self.cfg.state_file, prod_dir=prod_dir, bd_cwd=self.cfg.base_dir)
        self._hooks = load_hooks(self.cfg)
        self._consecutive_failures = 0

        def _signal_handler(signum, _frame):
            sig_name = signal.Signals(signum).name
            logger.warning("Received %s, writing stop file", sig_name)
            self.cfg.stop_file.write_text(f"received {sig_name}")

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

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
        self._emit(EventType.LOOP_STARTED)

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
            except StopRequested:
                break
            except RestartRequested:
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
        self._emit(EventType.LOOP_STOPPED, iterations=i)
        return False

    # -- signal and resource checks ----------------------------------------

    def _check_signals(self) -> None:
        """Read stop/restart signal files and raise accordingly."""
        if self.cfg.stop_file.exists():
            reason = self.cfg.stop_file.read_text() or "found empty stop file"
            self.cfg.stop_file.unlink()
            logger.warning("Stopping loop: %s", reason)
            raise StopRequested(reason)

        if self.cfg.restart_file.exists():
            reason = self.cfg.restart_file.read_text() or "found empty restart file"
            self.cfg.restart_file.unlink()
            logger.info("Restart requested: %s", reason)
            raise RestartRequested(reason)

    def _check_resources(self) -> None:
        """Stop if CPU, RAM, or disk usage exceeds the threshold."""
        cpu = round(psutil.cpu_percent(), 2)
        ram = round(psutil.virtual_memory().percent, 2)
        total_disk, used_disk, _ = shutil.disk_usage("/")
        disk = round(used_disk / total_disk * 100, 2)
        logger.info("CPU: %s%% | RAM: %s%% | Disk: %s%%", cpu, ram, disk)
        self._emit(EventType.RESOURCE_CHECK, cpu=cpu, ram=ram, disk=disk)

        threshold = self.cfg.vm_res_threshold
        if cpu > threshold or ram > threshold or disk > threshold:
            logger.warning(
                "Stopping loop: resource usage over %s%% threshold", threshold
            )
            raise StopRequested("resource usage over threshold")

    # -- issue acquisition -------------------------------------------------

    def _next_issue(self) -> Issue:
        """Return the next ready issue, blocking if none are available.

        Raises StopRequested when all issues are done (no open/blocked remain).
        """
        issue = bd.get_next_ready_issue(cwd=self.cfg.base_dir)
        if issue:
            logger.info("Retrieved issue: %r", issue)
            return issue

        self._check_all_done()
        logger.info("No ready issues. Waiting...")
        self._emit(EventType.LOOP_WAITING)
        while True:
            self._check_signals()
            issue = bd.get_next_ready_issue(cwd=self.cfg.base_dir)
            if issue:
                logger.info("Retrieved issue: %r", issue)
                return issue
            self._check_all_done()
            time.sleep(self.cfg.poll_interval)

    def _check_all_done(self) -> None:
        """Raise StopRequested if every issue is closed/done."""
        all_issues = bd.list_issues(cwd=self.cfg.base_dir)
        if not all_issues:
            return  # no issues at all -- keep waiting for new ones
        open_issues = [i for i in all_issues if i.status != "done"]
        if not open_issues:
            logger.info("All %d issue(s) are done", len(all_issues))
            raise StopRequested("all issues completed")

    # -- agent lifecycle ---------------------------------------------------

    def _create_agent(self, issue: Issue, iteration: int) -> Agent:
        """Build an Agent, claim the issue, and prepare git state."""
        extra_args, extra_kwargs = self._hooks.extra_args_kwargs(self.cfg, issue)
        extra_kwargs.setdefault("cwd", str(self.cfg.base_dir))
        agent = Agent(issue, self.cfg.model, iteration, *extra_args, bd_cwd=self.cfg.base_dir, **extra_kwargs)
        agent.claim_issue()
        self._emit(EventType.ISSUE_CLAIMED, issue_id=issue.id, title=issue.title)
        reset_git_state(issue.id, cwd=self.cfg.base_dir / PROD_WORKTREE)
        return agent

    def _process_issue(self, agent: Agent, issue: Issue, iteration: int) -> None:
        """Run the agent and handle its outcome."""
        iter_handler = self._add_iteration_log(iteration)
        self._hooks.pre_iter(self.cfg, issue, iteration)
        self._emit(EventType.ITER_STARTED, issue_id=issue.id, iteration=iteration)
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
        """Stream agent output to the logger and event bus."""
        logger.info("Starting agent")
        for line in agent.run(timeout=self.cfg.subprocess_timeout):
            stripped = line.rstrip()
            logger.info("[agent] %s", stripped)
            self._hooks.on_agent_output(stripped)
            self._emit(EventType.AGENT_OUTPUT, line=stripped, issue_id=agent.issue.id)
        logger.info("Agent finished: %s", agent.status)
        self._emit(EventType.AGENT_STATUS, status=str(agent.status), issue_id=agent.issue.id)

    def _handle_status(self, agent: Agent, issue: Issue) -> None:
        """Act on the agent's final status."""
        match agent.status:
            case AgentStatus.DONE:
                logger.info("Marking issue %s as done", issue.id)
                bd.close_issue(issue.id, cwd=self.cfg.base_dir)
                self._emit(EventType.ISSUE_DONE, issue_id=issue.id)
            case AgentStatus.HELP:
                logger.warning("Ralph needs help on issue %s", issue.id)
                self._state.cleanup_failed_iteration(status=bd.IssueStatus.BLOCKED)
                self._emit(EventType.ISSUE_HELP, issue_id=issue.id)
            case AgentStatus.BLOCKED:
                logger.info("Issue %s is blocked", issue.id)
                self._state.cleanup_failed_iteration(status=bd.IssueStatus.BLOCKED)
                self._emit(EventType.ISSUE_BLOCKED, issue_id=issue.id)
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
        self._emit(EventType.ITER_FAILED, error=str(exc))

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
            backoff = min(2**self._consecutive_failures, MAX_BACKOFF_SECONDS)
            logger.info("Backing off for %ss before retrying", backoff)
            time.sleep(backoff)

    # -- event helpers -----------------------------------------------------

    def _emit(self, event_type: EventType, **data) -> None:
        """Emit an event to the bus if one is attached."""
        if self.event_bus is not None:
            self.event_bus.emit(Event(event_type, data=data))

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
