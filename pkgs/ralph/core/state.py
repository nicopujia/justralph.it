"""State persistence for crash recovery."""

import json
import logging
import subprocess
from pathlib import Path

import bd

from ..utils.git import reset_git_state

logger = logging.getLogger(__name__)

_KEY_ISSUE_ID = "issue_id"
_KEY_ITERATION = "iteration"


class State:
    """Manages loop state on disk for crash recovery.

    Tracks the current issue_id and iteration. Write state before each
    iteration; clear it after. If the file exists on startup, the
    previous run crashed mid-iteration.
    """

    def __init__(self, file: Path) -> None:
        self._file = file
        self.issue_id: str | None = None

    def save(self, issue_id: str, iteration: int) -> None:
        """Persist the current issue and iteration index."""
        self.issue_id = issue_id
        self._file.write_text(
            json.dumps({_KEY_ISSUE_ID: issue_id, _KEY_ITERATION: iteration})
        )

    def clear(self) -> None:
        """Remove the state file and reset issue_id."""
        self.issue_id = None
        self._file.unlink(missing_ok=True)

    def check_crash_recovery(self) -> int:
        """Recover from a mid-iteration crash if a state file exists.

        Runs ``git reset --hard`` to discard partial changes, sets the
        interrupted issue back to open status and clears its assignee,
        then returns the saved iteration index so the loop can resume.

        Returns 0 if no crash was detected.
        """
        if not self._file.exists():
            return 0

        iteration = 0
        try:
            data = json.loads(self._file.read_text())
            self.issue_id = data.get(_KEY_ISSUE_ID)
            iteration = data.get(_KEY_ITERATION, 0)
        except (json.JSONDecodeError, OSError):
            logger.warning("Found corrupt state file; removing it")
            self.clear()
            return 0

        logger.warning(
            "Detected incomplete previous run (issue=%s, iteration=%s). Recovering...",
            self.issue_id or "?",
            iteration,
        )

        try:
            subprocess.run(
                ["git", "reset", "--hard"],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info("Ran git reset --hard")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error("git reset --hard failed: %s", e)

        if self.issue_id:
            self.cleanup_failed_iteration()

        self.clear()
        return iteration

    def cleanup_failed_iteration(self, status: str = bd.IssueStatus.OPEN) -> None:
        """Reset git state and update the issue after a failed iteration.

        Uses ``self.issue_id``. No-op if issue_id is not set.

        Args:
            status: Status to set on the issue (default: 'open')
        """
        if not self.issue_id:
            return
        logger.info("Cleaning up failed iteration for issue %s", self.issue_id)
        reset_git_state(self.issue_id)
        try:
            bd.update_issue(self.issue_id, status=status, assignee="")
            logger.info(
                "Set issue %s to %s and cleared assignee", self.issue_id, status
            )
        except RuntimeError:
            logger.error("Failed to update issue %s", self.issue_id)
