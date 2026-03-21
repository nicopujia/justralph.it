"""State persistence for crash recovery."""

import json
import logging
from pathlib import Path

import tasks

from ..utils.git import hard_reset, reset_git_state

logger = logging.getLogger(__name__)

_KEY_TASK_ID = "task_id"
_KEY_ITERATION = "iteration"


class State:
    """Manages loop state on disk for crash recovery.

    Tracks the current task_id and iteration. Write state before each
    iteration; clear it after. If the file exists on startup, the
    previous run crashed mid-iteration.
    """

    def __init__(
        self, file: Path, prod_dir: Path | None = None, dev_dir: Path | None = None, tasks_cwd: Path | None = None
    ) -> None:
        self._file = file
        self._prod_dir = prod_dir
        self._dev_dir = dev_dir
        self._tasks_cwd = tasks_cwd
        self.task_id: str | None = None

    def save(self, task_id: str, iteration: int) -> None:
        """Persist the current task and iteration index."""
        self.task_id = task_id
        self._file.write_text(
            json.dumps({_KEY_TASK_ID: task_id, _KEY_ITERATION: iteration})
        )

    def clear(self) -> None:
        """Remove the state file and reset task_id."""
        self.task_id = None
        self._file.unlink(missing_ok=True)

    def check_crash_recovery(self) -> int:
        """Recover from a mid-iteration crash if a state file exists.

        Runs ``git reset --hard`` to discard partial changes, sets the
        interrupted task back to open status and clears its assignee,
        then returns the saved iteration index so the loop can resume.

        Returns 0 if no crash was detected.
        """
        if not self._file.exists():
            return 0

        iteration = 0
        try:
            data = json.loads(self._file.read_text())
            # Support both old "issue_id" and new "task_id" keys
            self.task_id = data.get(_KEY_TASK_ID) or data.get("issue_id")
            iteration = data.get(_KEY_ITERATION, 0)
        except (json.JSONDecodeError, OSError):
            logger.warning("Found corrupt state file; removing it")
            self.clear()
            return 0

        logger.warning(
            "Detected incomplete previous run (task=%s, iteration=%s). Recovering...",
            self.task_id or "?",
            iteration,
        )

        try:
            hard_reset(cwd=self._prod_dir)
        except Exception as e:
            logger.error("git reset --hard (prod) failed: %s", e)
        if self._dev_dir:
            try:
                hard_reset(cwd=self._dev_dir)
            except Exception as e:
                logger.error("git reset --hard (dev) failed: %s", e)

        if self.task_id:
            self.cleanup_failed_iteration()

        self.clear()
        return iteration

    def cleanup_failed_iteration(self, status: str = tasks.TaskStatus.OPEN) -> None:
        """Reset git state and update the task after a failed iteration.

        Uses ``self.task_id``. No-op if task_id is not set.

        Args:
            status: Status to set on the task (default: 'open')
        """
        if not self.task_id:
            return
        logger.info("Cleaning up failed iteration for task %s", self.task_id)
        reset_git_state(self.task_id, cwd=self._prod_dir)
        try:
            tasks.update_task(self.task_id, status=status, assignee="", cwd=self._tasks_cwd)
            logger.info(
                "Set task %s to %s and cleared assignee", self.task_id, status
            )
        except RuntimeError:
            logger.error("Failed to update task %s", self.task_id)
