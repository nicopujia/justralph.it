"""Ralph Loop: processes tasks via OpenCode with hooks, events, and state recovery.

Uses OpenCode directly (via Agent class) for execution, preserving PROMPT.xml
and opencode.jsonc. Ralphy-cli is available for git operations (branch-per-task,
parallel, merge) but the agent prompt is ours.
"""

import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import tasks

from ..config import Config, PROJECT_ROOT, RALPHY_DIR_NAME
from .agent import Agent, AgentStatus
from .events import Event, EventBus, EventType
from .exceptions import BadAgentStatus
from .hooks import Hooks
from .state import State

logger = logging.getLogger(__name__)

MAX_BACKOFF_SECONDS = 300


@dataclass
class RunnerConfig(Config):
    """Configuration for the Ralph Loop runner."""

    tasks_file: Path = field(
        default=PROJECT_ROOT / "tasks.yaml",
        metadata={"help": "Path to tasks.yaml"},
    )
    project_dir: Path = field(
        default=PROJECT_ROOT,
        metadata={"help": "Project root directory"},
    )
    model: str = field(
        default="opencode-go/kimi-k2.5",
        metadata={"help": "Model for OpenCode (e.g., opencode/kimi-k2.5)"},
    )
    poll_interval: float = field(
        default=30.0,
        metadata={"help": "Seconds between polling for ready tasks"},
    )
    subprocess_timeout: float = field(
        default=600.0,
        metadata={"help": "Total timeout for OpenCode subprocess in seconds"},
    )
    progress_timeout: float = field(
        default=120.0,
        metadata={"help": "Kill agent if no output for this many seconds"},
    )
    max_iters: int = field(
        default=-1,
        metadata={"help": "Maximum iterations (-1 for no limit)"},
    )
    max_retries: int = field(
        default=-1,
        metadata={"help": "Max consecutive failures before stopping (-1 for no limit)"},
    )
    state_file: Path = field(
        default=PROJECT_ROOT / RALPHY_DIR_NAME / "state.json",
        metadata={"help": "Path to state file for crash recovery"},
    )
    stop_file: Path = field(
        default=PROJECT_ROOT / RALPHY_DIR_NAME / "stop.ralph",
        metadata={"help": "Write this file to stop the loop"},
    )
    restart_file: Path = field(
        default=PROJECT_ROOT / RALPHY_DIR_NAME / "restart.ralph",
        metadata={"help": "Write this file to restart the loop"},
    )


class RalphyRunner:
    """Processes tasks sequentially via OpenCode, with lifecycle hooks and events.

    Each iteration:
    1. Poll for next ready task (respects parent dependencies)
    2. Claim it (status -> in_progress)
    3. Spawn ``opencode run <task.as_xml()> --agent ralph``
    4. Parse agent status (DONE/HELP/BLOCKED)
    5. Close task or mark blocked
    6. Emit events for real-time UI streaming
    """

    def __init__(
        self,
        config: RunnerConfig,
        hooks: Hooks | None = None,
        bus: EventBus | None = None,
    ) -> None:
        self.cfg = config
        self._hooks = hooks
        self._bus = bus
        self._state = State(
            config.state_file,
            prod_dir=config.project_dir,
            tasks_cwd=config.project_dir,
        )
        self._consecutive_failures = 0
        self._current_iteration = 0

    def run(self) -> bool:
        """Main entry: recover state, run loop, clean up.

        Returns True if a restart was requested (caller should re-invoke).
        """
        i = self._state.check_crash_recovery()
        restart = False

        if self._hooks:
            self._hooks.pre_loop(self.cfg)
        self._emit(EventType.LOOP_STARTED)

        try:
            while True:
                if self.cfg.max_iters >= 0 and i >= self.cfg.max_iters:
                    logger.info("Reached max iterations (%s)", self.cfg.max_iters)
                    break

                self._check_signals()
                task = self._next_task()
                if task is None:
                    break  # all done

                self._current_iteration = i
                try:
                    self._process_task(task, i)
                    self._consecutive_failures = 0
                except Exception as exc:
                    self._handle_failure(exc)
                finally:
                    i += 1
                    self._state.clear()

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except _StopRequested as e:
            logger.info("Stopping: %s", e)
        except _RestartRequested:
            logger.info("Restart requested")
            restart = True
        finally:
            if self._hooks:
                self._hooks.post_loop(self.cfg, i)
            self._emit(EventType.LOOP_STOPPED, iterations=i)

        return restart

    # -- task acquisition ------------------------------------------------------

    def _next_task(self) -> tasks.Task | None:
        """Return the next ready task, waiting if none available.

        Returns None when all tasks are done (triggers loop exit).
        """
        task = tasks.get_next_ready_task(cwd=self.cfg.project_dir)
        if task:
            return task

        # Check if all done
        if self._check_all_done():
            return None

        # Wait for new tasks
        logger.info("No ready tasks. Waiting...")
        self._emit(EventType.LOOP_WAITING)
        while True:
            self._check_signals()
            task = tasks.get_next_ready_task(cwd=self.cfg.project_dir)
            if task:
                return task
            if self._check_all_done():
                return None
            time.sleep(self.cfg.poll_interval)

    def _check_all_done(self) -> bool:
        """Return True if every task is done (or no tasks exist)."""
        all_tasks = tasks.list_tasks(cwd=self.cfg.project_dir)
        if not all_tasks:
            return False  # no tasks yet, keep waiting
        open_tasks = [t for t in all_tasks if t.status != tasks.TaskStatus.DONE]
        if not open_tasks:
            logger.info("All %d task(s) done", len(all_tasks))
            return True
        return False

    # -- task processing -------------------------------------------------------

    def _process_task(self, task: tasks.Task, iteration: int) -> None:
        """Claim task, run agent, handle result."""
        self._state.save(task.id, iteration)

        # Claim
        agent = Agent(
            task,
            self.cfg.model,
            iteration,
            tasks_cwd=self.cfg.project_dir,
            cwd=str(self.cfg.project_dir),
        )
        agent.claim_task()
        self._emit(EventType.TASK_CLAIMED, task_id=task.id, title=task.title)

        # Pre-iter hook
        if self._hooks:
            self._hooks.pre_iter(self.cfg, task, iteration)
        self._emit(EventType.ITER_STARTED, task_id=task.id, iteration=iteration)

        # Run agent
        error: Exception | None = None
        try:
            for line in agent.run(
                timeout=self.cfg.subprocess_timeout,
                progress_timeout=self.cfg.progress_timeout,
            ):
                stripped = line.rstrip()
                logger.info("[agent] %s", stripped)
                if self._hooks:
                    self._hooks.on_agent_output(stripped)
                self._emit(EventType.AGENT_OUTPUT, line=stripped, task_id=task.id)

            logger.info("Agent finished: %s", agent.status)
            self._emit(EventType.AGENT_STATUS, status=str(agent.status), task_id=task.id)
            self._handle_status(agent, task, iteration)
            self._emit(EventType.ITER_COMPLETED, task_id=task.id, iteration=iteration)
        except Exception as exc:
            error = exc
            raise
        finally:
            if self._hooks:
                self._hooks.post_iter(self.cfg, task, iteration, agent.status, error)

    def _handle_status(self, agent: Agent, task: tasks.Task, iteration: int) -> None:
        """Act on agent's final status."""
        match agent.status:
            case AgentStatus.DONE:
                tasks.close_task(task.id, cwd=self.cfg.project_dir)
                self._push_to_remote()
                self._emit(EventType.TASK_DONE, task_id=task.id)
                logger.info("Task %s completed", task.id)

            case AgentStatus.HELP:
                logger.warning("Agent needs help on task %s", task.id)
                tasks.update_task(
                    task.id,
                    status=tasks.TaskStatus.BLOCKED,
                    append_notes="Agent requested human help",
                    cwd=self.cfg.project_dir,
                )
                self._emit(EventType.TASK_HELP, task_id=task.id)

            case AgentStatus.BLOCKED:
                logger.info("Task %s blocked (new blocker filed)", task.id)
                tasks.update_task(
                    task.id,
                    status=tasks.TaskStatus.BLOCKED,
                    append_notes="Agent found new blocker task",
                    cwd=self.cfg.project_dir,
                )
                self._emit(EventType.TASK_BLOCKED, task_id=task.id)

            case _:
                raise BadAgentStatus(f"Unexpected status: {agent.status}")

    def _push_to_remote(self) -> None:
        """Push current branch to origin (best-effort, no-op if no remote)."""
        try:
            result = subprocess.run(
                ["git", "remote"], capture_output=True, text=True,
                cwd=self.cfg.project_dir,
            )
            if "origin" not in result.stdout:
                return
            subprocess.run(
                ["git", "push", "origin", "HEAD"],
                capture_output=True, text=True, cwd=self.cfg.project_dir,
            )
            logger.info("Pushed to origin")
        except Exception as e:
            logger.warning("Git push failed (non-fatal): %s", e)

    # -- failure handling ------------------------------------------------------

    def _handle_failure(self, exc: Exception) -> None:
        """Log, clean up, apply backoff."""
        self._consecutive_failures += 1
        logger.exception(
            "Iteration failed (consecutive: %s)", self._consecutive_failures
        )
        self._state.cleanup_failed_iteration()
        self._emit(EventType.ITER_FAILED, error=str(exc))

        if (
            self.cfg.max_retries >= 0
            and self._consecutive_failures > self.cfg.max_retries
        ):
            self.cfg.stop_file.write_text(
                f"exceeded max retries ({self.cfg.max_retries})"
            )
            logger.error("Max retries exceeded; stopping")
        else:
            backoff = min(2**self._consecutive_failures, MAX_BACKOFF_SECONDS)
            logger.info("Backing off %ss", backoff)
            time.sleep(backoff)

    # -- signals ---------------------------------------------------------------

    def _check_signals(self) -> None:
        """Check stop/restart signal files."""
        if self.cfg.stop_file.exists():
            reason = self.cfg.stop_file.read_text() or "stop file found"
            self.cfg.stop_file.unlink()
            raise _StopRequested(reason)

        if self.cfg.restart_file.exists():
            reason = self.cfg.restart_file.read_text() or "restart file found"
            self.cfg.restart_file.unlink()
            raise _RestartRequested(reason)

    # -- events ----------------------------------------------------------------

    def _emit(self, event_type: EventType, **data) -> None:
        """Emit an event if a bus is attached."""
        if self._bus is not None:
            self._bus.emit(Event(event_type, data=data))


class _StopRequested(Exception):
    pass


class _RestartRequested(Exception):
    pass
