"""Git utilities for branch and repo management."""

import logging
import subprocess

logger = logging.getLogger(__name__)


def cleanup_branch(issue_id: str) -> None:
    """Delete the ralph/[issue-id] branch if it exists.

    Args:
        issue_id: The issue ID (e.g., 'bd-123')
    """
    branch_name = f"ralph/{issue_id}"
    try:
        # Check if branch exists
        result = subprocess.run(
            ["git", "rev-parse", "--verify", branch_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            logger.info("Branch %s exists; deleting it", branch_name)
            subprocess.run(
                ["git", "branch", "-D", branch_name],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info("Deleted branch %s", branch_name)
        else:
            logger.debug("Branch %s does not exist; nothing to clean up", branch_name)
    except subprocess.CalledProcessError as e:
        logger.warning("Failed to delete branch %s: %s", branch_name, e.stderr)


def ensure_on_main() -> None:
    """Ensure the current branch is main. Checkout main if not already on it."""
    try:
        # Check current branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        current_branch = result.stdout.strip()

        if current_branch != "main":
            logger.info("Currently on branch %s; checking out main", current_branch)
            subprocess.run(
                ["git", "checkout", "main"],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info("Checked out main")
        else:
            logger.debug("Already on main branch")
    except subprocess.CalledProcessError as e:
        logger.error("Failed to checkout main: %s", e.stderr)
        raise
