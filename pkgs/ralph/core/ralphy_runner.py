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
from xml.sax.saxutils import escape as xml_escape

import yaml

import tasks

from ..config import Config, PROJECT_ROOT, RALPHY_DIR_NAME
from .agent import Agent, AgentStatus
from .events import Event, EventBus, EventType
from .exceptions import BadAgentStatus
from .hooks import Hooks
from .state import State

logger = logging.getLogger(__name__)


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
    progress_timeout: float = field(
        default=120.0,
        metadata={"help": "Kill agent if no output for this many seconds"},
    )
    max_task_duration: float = field(
        default=900.0,
        metadata={"help": "Hard cap per task regardless of output activity (seconds)"},
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
        self._loop_start_time: float = time.monotonic()

    def run(self) -> bool:
        """Main entry: recover state, run loop, clean up.

        Returns True if a restart was requested (caller should re-invoke).
        """
        i = self._state.check_crash_recovery()
        restart = False
        self._loop_start_time = time.monotonic()

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
        Emits LOOP_HEARTBEAT each poll cycle and LOOP_STALLED if all
        remaining open tasks are blocked (no progress possible).
        """
        task = tasks.get_next_ready_task(cwd=self.cfg.project_dir)
        if task:
            return task

        if self._check_all_done():
            return None

        # Stall check before first wait
        if self._check_all_stalled():
            return None

        logger.info("No ready tasks. Waiting...")
        self._emit(EventType.LOOP_WAITING)
        loop_start = self._loop_start_time
        while True:
            self._check_signals()
            task = tasks.get_next_ready_task(cwd=self.cfg.project_dir)
            if task:
                return task
            if self._check_all_done():
                return None
            if self._check_all_stalled():
                return None
            elapsed = time.monotonic() - loop_start
            counts = self._task_counts()
            ready_count = self._ready_task_count()
            self._emit(
                EventType.LOOP_HEARTBEAT,
                loop_state="waiting_for_tasks",
                task_counts=counts,
                elapsed_seconds=round(elapsed, 1),
                ready_task_count=ready_count,
            )
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

    def _check_all_stalled(self) -> bool:
        """Return True (and emit LOOP_STALLED) if no task can ever become ready.

        Detects two stall conditions:
        1. All non-done tasks are BLOCKED (no OPEN, no IN_PROGRESS).
        2. Only IN_PROGRESS tasks remain but none are being processed by this
           runner (orphaned from a crash). These are reset to OPEN so the loop
           can pick them up again.
        """
        all_tasks = tasks.list_tasks(cwd=self.cfg.project_dir)
        if not all_tasks:
            return False
        non_done = [t for t in all_tasks if t.status != tasks.TaskStatus.DONE]
        if not non_done:
            return False  # _check_all_done will catch this
        open_tasks = [t for t in non_done if t.status == tasks.TaskStatus.OPEN]
        in_progress = [t for t in non_done if t.status == tasks.TaskStatus.IN_PROGRESS]

        if open_tasks:
            return False  # tasks available

        # Self-heal: orphaned IN_PROGRESS tasks (not being processed by us)
        if in_progress and not open_tasks:
            for t in in_progress:
                logger.warning(
                    "Resetting orphaned IN_PROGRESS task %s to OPEN", t.id,
                )
                tasks.update_task(
                    t.id,
                    status=tasks.TaskStatus.OPEN,
                    assignee="",
                    append_notes="Auto-reset: orphaned IN_PROGRESS task detected by loop",
                    cwd=self.cfg.project_dir,
                )
            return False  # retry -- tasks are now OPEN

        # All remaining tasks are BLOCKED -- no forward progress possible
        blocked_ids = [t.id for t in non_done]
        logger.warning("Loop stalled: all remaining tasks are blocked: %s", blocked_ids)
        self._emit(
            EventType.LOOP_STALLED,
            blocked_task_ids=blocked_ids,
            reason="all_tasks_blocked",
        )
        return True

    def _task_counts(self) -> dict[str, int]:
        """Return a status -> count dict for all tasks."""
        all_tasks = tasks.list_tasks(cwd=self.cfg.project_dir)
        counts: dict[str, int] = {}
        for t in all_tasks:
            counts[str(t.status)] = counts.get(str(t.status), 0) + 1
        return counts

    def _ready_task_count(self) -> int:
        """Return how many OPEN tasks have no blocking parent."""
        all_tasks = tasks.list_tasks(cwd=self.cfg.project_dir)
        done_ids = {t.id for t in all_tasks if t.status == tasks.TaskStatus.DONE}
        return sum(
            1 for t in all_tasks
            if t.status == tasks.TaskStatus.OPEN
            and (not t.parent or t.parent in done_ids)
        )

    # -- timeout scaling -------------------------------------------------------

    # Multipliers for max_task_duration and progress_timeout based on complexity label
    _COMPLEXITY_SCALE: dict[str, tuple[float, float]] = {
        "low": (0.33, 0.5),      # 5min total, 1min progress (default 15min/2min)
        "medium": (1.0, 1.0),    # use configured defaults
        "high": (1.5, 1.5),      # 22.5min total, 3min progress
    }

    def _task_timeouts(self, task: tasks.Task) -> tuple[float, float]:
        """Return (max_task_duration, progress_timeout) scaled by task complexity."""
        complexity = "medium"
        for label in task.labels:
            if label.startswith("complexity:"):
                complexity = label.split(":", 1)[1]
                break
        dur_scale, prog_scale = self._COMPLEXITY_SCALE.get(complexity, (1.0, 1.0))
        return (
            self.cfg.max_task_duration * dur_scale,
            self.cfg.progress_timeout * prog_scale,
        )

    # -- context building ------------------------------------------------------

    def _build_context_xml(self, task: tasks.Task) -> str:
        """Build project context XML so the agent starts with full awareness.

        Includes: project metadata, completed tasks, remaining tasks,
        and a diff summary of the most recently completed task.
        """
        parts: list[str] = ["<Context>"]

        # 1. Project metadata from .ralphy/config.yaml
        config_path = self.cfg.project_dir / ".ralphy" / "config.yaml"
        if config_path.exists():
            try:
                cfg = yaml.safe_load(config_path.read_text()) or {}
                proj = cfg.get("project", {})
                if proj:
                    parts.append("  <Project>")
                    for k, v in proj.items():
                        if v:
                            tag = k.replace("_", " ").title().replace(" ", "")
                            parts.append(f"    <{tag}>{xml_escape(str(v))}</{tag}>")
                    parts.append("  </Project>")
            except Exception:
                pass

        # 2. Task graph: completed + remaining
        all_tasks = tasks.list_tasks(cwd=self.cfg.project_dir)
        done = [t for t in all_tasks if t.status == tasks.TaskStatus.DONE]
        remaining = [t for t in all_tasks if t.status != tasks.TaskStatus.DONE and t.id != task.id]

        if done:
            parts.append("  <CompletedTasks>")
            for t in done:
                parts.append(f'    <Done id="{xml_escape(t.id)}">{xml_escape(t.title)}</Done>')
            parts.append("  </CompletedTasks>")

        if remaining:
            parts.append("  <RemainingTasks>")
            for t in remaining:
                parts.append(f'    <Pending id="{xml_escape(t.id)}" priority="{t.priority}">{xml_escape(t.title)}</Pending>')
            parts.append("  </RemainingTasks>")

        # 3. Diff summary from last completed task
        diff_stat = self._last_task_diff_stat()
        if diff_stat:
            parts.append("  <PreviousTaskChanges>")
            parts.append(f"    {xml_escape(diff_stat)}")
            parts.append("  </PreviousTaskChanges>")

        parts.append("</Context>\n")
        return "\n".join(parts)

    def _last_task_diff_stat(self) -> str:
        """Get git diff --stat for the last commit (previous task's work)."""
        try:
            result = subprocess.run(
                ["git", "diff", "--stat", "HEAD~1", "HEAD"],
                capture_output=True, text=True, cwd=self.cfg.project_dir,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        return ""

    # -- task processing -------------------------------------------------------

    def _process_task(self, task: tasks.Task, iteration: int) -> None:
        """Claim task, run agent, handle result."""
        self._state.save(task.id, iteration)

        # Build context so agent starts with full project awareness
        context_xml = self._build_context_xml(task)

        # Claim
        agent = Agent(
            task,
            self.cfg.model,
            iteration,
            tasks_cwd=self.cfg.project_dir,
            context_xml=context_xml,
            cwd=str(self.cfg.project_dir),
        )
        agent.claim_task()
        self._emit(EventType.TASK_CLAIMED, task_id=task.id, title=task.title)

        # Pre-iter hook
        if self._hooks:
            self._hooks.pre_iter(self.cfg, task, iteration)
        self._emit(EventType.ITER_STARTED, task_id=task.id, iteration=iteration)

        # Run agent with complexity-scaled timeouts
        max_dur, prog_timeout = self._task_timeouts(task)
        error: Exception | None = None
        task_start = time.monotonic()
        output_line_count = 0
        try:
            for line in agent.run(
                timeout=max_dur,
                progress_timeout=prog_timeout,
            ):
                stripped = line.rstrip()
                output_line_count += 1
                logger.info("[agent] %s", stripped)
                if self._hooks:
                    self._hooks.on_agent_output(stripped)
                self._emit(EventType.AGENT_OUTPUT, line=stripped, task_id=task.id)
                self._emit(
                    EventType.TASK_PROGRESS,
                    task_id=task.id,
                    elapsed_seconds=round(time.monotonic() - task_start, 1),
                    output_line_count=output_line_count,
                    loop_state="processing_task",
                )

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
                diff = self._capture_diff()
                if diff:
                    self._emit(EventType.TASK_DIFF, task_id=task.id, diff=diff)
                pushed = self._push_to_remote(task.id)
                self._emit(EventType.TASK_DONE, task_id=task.id, pushed=pushed)
                logger.info("Task %s completed (pushed=%s)", task.id, pushed)

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

    def _capture_diff(self) -> str:
        """Capture git diff for the last commit (task just completed)."""
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD~1", "HEAD"],
                capture_output=True, text=True, cwd=self.cfg.project_dir,
            )
            return result.stdout.strip()
        except Exception as e:
            logger.warning("Failed to capture diff: %s", e)
            return ""

    def _push_to_remote(self, task_id: str = "") -> bool:
        """Push current branch to origin, emit success/failure events.

        Returns True if push succeeded, False otherwise.
        """
        try:
            result = subprocess.run(
                ["git", "remote"], capture_output=True, text=True,
                cwd=self.cfg.project_dir,
            )
            if "origin" not in result.stdout:
                return False

            # Get remote URL for event data
            url_result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, cwd=self.cfg.project_dir,
            )
            remote_url = url_result.stdout.strip()

            # Get current commit SHA
            sha_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, cwd=self.cfg.project_dir,
            )
            commit_sha = sha_result.stdout.strip()[:8]

            push_result = subprocess.run(
                ["git", "push", "origin", "HEAD"],
                capture_output=True, text=True, cwd=self.cfg.project_dir,
            )
            if push_result.returncode == 0:
                logger.info("Pushed to origin (%s)", remote_url)
                self._emit(
                    EventType.GIT_PUSH_SUCCESS,
                    task_id=task_id,
                    remote_url=remote_url,
                    commit_sha=commit_sha,
                )
                return True
            else:
                error_msg = push_result.stderr.strip() or "unknown push error"
                logger.warning("Git push failed: %s", error_msg)
                self._emit(
                    EventType.GIT_PUSH_FAILED,
                    task_id=task_id,
                    remote_url=remote_url,
                    error=error_msg,
                )
                return False
        except Exception as e:
            logger.warning("Git push failed (non-fatal): %s", e)
            self._emit(
                EventType.GIT_PUSH_FAILED,
                task_id=task_id,
                error=str(e),
            )
            return False

    # -- failure handling ------------------------------------------------------

    def _handle_failure(self, exc: Exception) -> None:
        """Mark failed task as BLOCKED, emit TASK_HELP, and move on.

        Instead of retrying with backoff, the task is blocked so the user
        can inspect the error and PATCH it back to OPEN via the REST API.
        """
        task_id = self._state.task_id
        logger.exception("Iteration failed for task %s", task_id)

        # Reset git state and mark task BLOCKED (clears assignee too)
        self._state.cleanup_failed_iteration(status=tasks.TaskStatus.BLOCKED)

        # Append error details to the task notes
        if task_id:
            try:
                tasks.update_task(
                    task_id,
                    append_notes=str(exc),
                    cwd=self.cfg.project_dir,
                )
            except RuntimeError:
                logger.error("Failed to append error notes to task %s", task_id)

        self._emit(EventType.ITER_FAILED, error=str(exc))
        self._emit(EventType.TASK_HELP, task_id=task_id, error=str(exc))

        # Reset counter -- we're moving to the next task, not retrying
        self._consecutive_failures = 0

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
