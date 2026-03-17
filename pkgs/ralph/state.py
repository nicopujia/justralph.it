"""State persistence for crash recovery."""

import json
import logging
import subprocess
from pathlib import Path

import bd

from .git import cleanup_branch, ensure_on_main

logger = logging.getLogger(__name__)


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
        - Sets the interrupted issue back to open status.
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

        # ensure we're on main and delete the branch if it exists
        if issue_id:
            try:
                ensure_on_main()
            except subprocess.CalledProcessError:
                logger.warning("Could not checkout main; branch cleanup may fail")
            cleanup_branch(issue_id)

        # set the issue back to open
        if issue_id:
            try:
                bd.update_issue(issue_id, status="open")
                logger.info("Set issue %s back to open", issue_id)
            except RuntimeError:
                logger.error("Failed to reopen issue %s", issue_id)

        self.clear()
        return iteration
