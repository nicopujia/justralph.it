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

from ..config import (
    BRANCH_PREFIX,
    DEV_WORKTREE,
    LOGS_DIR,
    PROD_WORKTREE,
    PROJECT_ROOT,
    RALPH_DIR,
    RALPH_DIR_NAME,
    Config,
)
from ..core.agent import Agent, AgentStatus
from ..core.events import Event, EventBus, EventType
from ..core.exceptions import RestartRequested, StopRequested
from ..core.hooks import load_hooks
from ..core.state import State
from ..utils.backup import prune_old_snapshots, snapshot_issues
from ..utils.git import (
    cleanup_branch,
    cleanup_issue_tags,
    create_tag,
    done_tag,
    ensure_on_main,
    get_latest_tag,
    hard_reset,
    has_changes_since,
    is_worktree_clean,
    merge_from,
    pre_iter_tag,
    rollback_to_tag,
    sync_to_branch,
)
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
    progress_timeout: float = field(
        default=120.0,
        metadata={"help": "Kill agent if no output for this many seconds"},
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
            default=argparse.SUPPRESS,
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

        self._prod_dir = self.cfg.base_dir / PROD_WORKTREE
        self._dev_dir = self.cfg.base_dir / DEV_WORKTREE
        self._backup_dir = self._prod_dir / RALPH_DIR_NAME / "backups"
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        self._state = State(self.cfg.state_file, prod_dir=self._prod_dir, dev_dir=self._dev_dir, bd_cwd=self.cfg.base_dir)
        self._hooks = load_hooks(self.cfg)
        self._consecutive_failures = 0
        self._current_iteration = 0

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
            processed = False
            try:
                self._check_signals()
                self._check_resources()
                issue = self._next_issue()
                agent = self._create_agent(issue, i)
                processed = True
                self._process_issue(agent, issue, i)
                self._consecutive_failures = 0
                self._emit(EventType.ITER_COMPLETED, issue_id=issue.id, iteration=i)
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
                if processed:
                    self._verify_worktree_health()
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
        """Build an Agent, claim the issue, and prepare git/backup state.

        1. Tag prod/main as a rollback checkpoint
        2. Snapshot bd issues for rollback
        3. Sync dev worktree to main
        4. Reset git state in dev
        5. Create agent (cwd=base_dir, agent cd's into ./dev/ per PROMPT.xml)
        """
        # Checkpoint: tag prod/main before any work
        tag = pre_iter_tag(issue.id, iteration)
        create_tag(tag, message=f"pre-iter: {issue.id} iter {iteration}", cwd=self._prod_dir)
        self._emit(EventType.TAG_CREATED, tag=tag)

        # Snapshot bd issues for potential rollback, prune old ones
        snapshot_issues(iteration, self._backup_dir, bd_cwd=self.cfg.base_dir)
        prune_old_snapshots(self._backup_dir)

        # Prepare dev worktree: sync to main, clean up old issue branch
        # (can't use reset_git_state here -- it tries checkout main, which
        # is already owned by the prod worktree)
        sync_to_branch("main", cwd=self._dev_dir)
        cleanup_branch(issue.id, cwd=self._dev_dir)

        # Create agent with cwd=base_dir (where opencode.jsonc + PROMPT.xml live)
        extra_args, extra_kwargs = self._hooks.extra_args_kwargs(self.cfg, issue)
        extra_kwargs.setdefault("cwd", str(self.cfg.base_dir))
        agent = Agent(issue, self.cfg.model, iteration, *extra_args, bd_cwd=self.cfg.base_dir, **extra_kwargs)
        agent.claim_issue()
        self._emit(EventType.ISSUE_CLAIMED, issue_id=issue.id, title=issue.title)
        return agent

    def _process_issue(self, agent: Agent, issue: Issue, iteration: int) -> None:
        """Run the agent and handle its outcome."""
        self._current_iteration = iteration
        # Save state FIRST so cleanup_failed_iteration can find the issue_id
        # if hooks or logging throw before the agent runs
        self._state.save(issue.id, iteration)
        iter_handler = None
        iter_handler = self._add_iteration_log(iteration)
        self._hooks.pre_iter(self.cfg, issue, iteration)
        self._emit(EventType.ITER_STARTED, issue_id=issue.id, iteration=iteration)

        iter_error: Exception | None = None
        try:
            self._run_agent(agent)
            self._handle_status(agent, issue, iteration)
        except Exception as exc:
            iter_error = exc
            raise
        finally:
            self._hooks.post_iter(self.cfg, issue, iteration, agent.status, iter_error)
            if iter_handler is not None:
                self._remove_iteration_log(iter_handler)

    def _run_agent(self, agent: Agent) -> None:
        """Stream agent output to the logger and event bus."""
        logger.info("Starting agent")
        for line in agent.run(
            timeout=self.cfg.subprocess_timeout,
            progress_timeout=self.cfg.progress_timeout,
        ):
            stripped = line.rstrip()
            logger.info("[agent] %s", stripped)
            self._hooks.on_agent_output(stripped)
            self._emit(EventType.AGENT_OUTPUT, line=stripped, issue_id=agent.issue.id)
        logger.info("Agent finished: %s", agent.status)
        self._emit(EventType.AGENT_STATUS, status=str(agent.status), issue_id=agent.issue.id)

    def _handle_status(self, agent: Agent, issue: Issue, iteration: int) -> None:
        """Validate agent work and promote to prod on success."""
        tag = pre_iter_tag(issue.id, iteration)
        branch = f"{BRANCH_PREFIX}{issue.id}"

        match agent.status:
            case AgentStatus.DONE:
                # Validate: agent produced changes in dev
                if not has_changes_since("main", cwd=self._dev_dir):
                    logger.error("Agent returned DONE but produced no changes")
                    bd.update_issue(
                        issue.id, status=bd.IssueStatus.BLOCKED,
                        append_notes="validation failed: no changes after DONE",
                        cwd=self.cfg.base_dir,
                    )
                    self._emit(EventType.VALIDATION_FAILED, issue_id=issue.id, reason="no_changes")
                    return

                # Promote: merge agent's branch into prod/main
                ensure_on_main(cwd=self._prod_dir)
                if not merge_from(branch, cwd=self._prod_dir):
                    logger.error("Merge of %s into prod/main failed", branch)
                    rollback_to_tag(tag, cwd=self._prod_dir)
                    bd.update_issue(
                        issue.id, status=bd.IssueStatus.BLOCKED,
                        append_notes="merge to prod failed -- rolled back",
                        cwd=self.cfg.base_dir,
                    )
                    self._emit(EventType.ROLLBACK, issue_id=issue.id, tag=tag)
                    return

                # Success
                create_tag(done_tag(issue.id), message=f"completed: {issue.id}", cwd=self._prod_dir)
                cleanup_issue_tags(issue.id, cwd=self._prod_dir)
                bd.close_issue(issue.id, cwd=self.cfg.base_dir)
                self._emit(EventType.ISSUE_DONE, issue_id=issue.id)

            case AgentStatus.HELP:
                logger.warning("Ralph needs help on issue %s", issue.id)
                self._ensure_prod_clean(tag)
                self._state.cleanup_failed_iteration(status=bd.IssueStatus.BLOCKED)
                self._emit(EventType.ISSUE_HELP, issue_id=issue.id)

            case AgentStatus.BLOCKED:
                logger.info("Issue %s is blocked", issue.id)
                self._ensure_prod_clean(tag)
                self._state.cleanup_failed_iteration(status=bd.IssueStatus.BLOCKED)
                self._emit(EventType.ISSUE_BLOCKED, issue_id=issue.id)

            case _:
                logger.warning("Unexpected status %s for %s", agent.status, issue.id)
                self._ensure_prod_clean(tag)
                self._state.cleanup_failed_iteration()
                raise ValueError(f"Unexpected agent status: {agent.status}")

    def _ensure_prod_clean(self, fallback_tag: str) -> None:
        """Verify prod worktree is clean; rollback to tag if not."""
        if not is_worktree_clean(cwd=self._prod_dir):
            logger.warning("Prod worktree dirty; rolling back to %s", fallback_tag)
            rollback_to_tag(fallback_tag, cwd=self._prod_dir)
            self._emit(EventType.ROLLBACK, tag=fallback_tag)

    # -- failure handling --------------------------------------------------

    def _handle_failure(self, exc: Exception) -> None:
        """Log the failure, clean up, rollback prod, and apply backoff."""
        self._consecutive_failures += 1
        logger.exception(
            "Failed unexpectedly (consecutive failures: %s)",
            self._consecutive_failures,
        )

        # Rollback prod if a pre-iter tag exists for this iteration
        if self._state.issue_id:
            tag = pre_iter_tag(self._state.issue_id, self._current_iteration)
            self._ensure_prod_clean(tag)

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

    def _verify_worktree_health(self) -> None:
        """Ensure prod worktree is clean after each iteration."""
        if is_worktree_clean(cwd=self._prod_dir):
            return
        logger.warning("Prod worktree not clean after iteration; resetting")
        last_good = (
            get_latest_tag("done/*", cwd=self._prod_dir)
            or get_latest_tag("pre-iter/*", cwd=self._prod_dir)
        )
        if last_good:
            rollback_to_tag(last_good, cwd=self._prod_dir)
        else:
            hard_reset(cwd=self._prod_dir)
            ensure_on_main(cwd=self._prod_dir)

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
