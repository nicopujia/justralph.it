"""State persistence for crash recovery."""

import json
import logging
import subprocess
from pathlib import Path

import bd

from .git import reset_git_state

logger = logging.getLogger(__name__)


def cleanup_failed_iteration(issue_id: str, status: str = "open") -> None:
    """Clean up after a failed iteration: reset git state and update issue.

    This is used when Ralph fails to complete an issue for any reason
    (exception, timeout, bad status, needs help, blocked, etc).
    It ensures the issue is properly updated and git is in a clean state.

    Args:
        issue_id: The issue ID (e.g., 'bd-123')
        status: Status to set on the issue (default: 'open')
    """
    logger.info("Cleaning up failed iteration for issue %s", issue_id)
    reset_git_state(issue_id)
    try:
        bd.update_issue(issue_id, status=status, assignee="")
        logger.info("Set issue %s to %s and cleared assignee", issue_id, status)
    except RuntimeError:
        logger.error("Failed to update issue %s", issue_id)


class State:
    """Manages loop state on disk for crash recovery.

    Write state before each iteration; clear it after. If the file
    exists on startup, the previous run crashed mid-iteration.
    """

    def __init__(self, file: Path) -> None:
        self._file = file

    def save(self, issue_id: str, iteration: int) -> None:
        """Persist the current issue and iteration index."""
        self._file.write_text(
            json.dumps({"issue_id": issue_id, "iteration": iteration})
        )

    def clear(self) -> None:
        """Remove the state file (idempotent)."""
        self._file.unlink(missing_ok=True)

    def check_crash_recovery(self) -> int:
        """Recover from a mid-iteration crash if a state file exists.

        - Runs ``git reset --hard`` to discard partial changes.
        - Sets the interrupted issue back to open status and clears assignee.
        - Returns the saved iteration index so the loop can resume from it.

        Returns 0 if no crash was detected.
        """
        if not self._file.exists():
            return 0

        issue_id = None
        iteration = 0
        try:
            data = json.loads(self._file.read_text())
            issue_id = data.get("issue_id")
            iteration = data.get("iteration", 0)
        except (json.JSONDecodeError, OSError):
            logger.warning("Found corrupt state file; removing it")
            self.clear()
            return 0

        logger.warning(
            "Detected incomplete previous run (issue=%s, iteration=%s). Recovering...",
            issue_id or "?",
            iteration,
        )

        # discard any partial changes from the crashed iteration
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

        # reset git state and reopen the issue
        if issue_id:
            cleanup_failed_iteration(issue_id)

        self.clear()
        return iteration
