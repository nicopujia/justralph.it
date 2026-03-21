"""Git utilities for branch and repo management."""

import logging
import subprocess
from pathlib import Path

from ..config import BRANCH_PREFIX, DONE_TAG_PREFIX, MAIN_BRANCH, PRE_ITER_TAG_PREFIX

logger = logging.getLogger(__name__)

INITIAL_COMMIT_MSG = "initial commit"


def _run(
    *args: str, cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run a git command, returning the completed process."""
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=check, cwd=cwd
    )


def is_repo(path: Path) -> bool:
    """Return True if *path* is inside a git repository."""
    return _run("rev-parse", "--git-dir", cwd=path, check=False).returncode == 0



def has_remote(repo: Path, name: str) -> bool:
    """Return True if a remote named *name* exists."""
    result = _run("remote", cwd=repo, check=False)
    return name in result.stdout.splitlines()


def add_remote(repo: Path, name: str, url: str) -> None:
    """Add a named remote, or update URL if it already exists.

    Args:
        repo: Root of the repo (bare or worktree).
        name: Remote name (e.g. "origin").
        url: Remote URL.
    """
    if has_remote(repo, name):
        _run("remote", "set-url", name, url, cwd=repo)
        logger.info("Updated remote %s -> %s", name, url)
    else:
        _run("remote", "add", name, url, cwd=repo)
        logger.info("Added remote %s -> %s", name, url)


def push(branch: str = MAIN_BRANCH, remote: str = "origin", cwd: Path | None = None) -> None:
    """Push a branch to a remote.

    Args:
        branch: Branch to push.
        remote: Remote name.
        cwd: Directory to run from (worktree or bare root).
    """
    _run("push", "-u", remote, branch, cwd=cwd)
    logger.info("Pushed %s to %s", branch, remote)


def hard_reset(cwd: Path | None = None) -> None:
    """Run ``git reset --hard`` to discard uncommitted changes.

    Args:
        cwd: Directory to run in (should be a worktree, not bare root).
    """
    _run("reset", "--hard", cwd=cwd)
    logger.info("Ran git reset --hard in %s", cwd or "cwd")


def cleanup_branch(task_id: str, cwd: Path | None = None) -> None:
    """Delete the ralph/[task-id] branch if it exists.

    Args:
        task_id: The task ID (e.g., 'task-001')
        cwd: Directory to run git commands from.
    """
    branch_name = f"{BRANCH_PREFIX}{task_id}"
    result = _run("rev-parse", "--verify", branch_name, cwd=cwd, check=False)
    if result.returncode == 0:
        logger.info("Branch %s exists; deleting it", branch_name)
        _run("branch", "-D", branch_name, cwd=cwd)
        logger.info("Deleted branch %s", branch_name)
    else:
        logger.debug("Branch %s does not exist; nothing to clean up", branch_name)


def ensure_on_main(cwd: Path | None = None) -> None:
    """Ensure the current branch is main. Checkout main if not already on it.

    Args:
        cwd: Directory to run git commands from (should be a worktree).
    """
    result = _run("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    current_branch = result.stdout.strip()

    if current_branch != MAIN_BRANCH:
        logger.info("Currently on branch %s; checking out main", current_branch)
        _run("checkout", MAIN_BRANCH, cwd=cwd)
        logger.info("Checked out main")
    else:
        logger.debug("Already on main branch")


def reset_git_state(task_id: str, cwd: Path | None = None) -> None:
    """Reset git state: ensure on main and delete task branch.

    Args:
        task_id: The task ID (e.g., 'task-001')
        cwd: Directory to run git commands from (should be a worktree).
    """
    ensure_on_main(cwd=cwd)
    cleanup_branch(task_id, cwd=cwd)


# -- tagging ---------------------------------------------------------------


def pre_iter_tag(task_id: str, iteration: int) -> str:
    """Tag name for a pre-iteration checkpoint."""
    return f"{PRE_ITER_TAG_PREFIX}/{task_id}/{iteration}"


def done_tag(task_id: str) -> str:
    """Tag name for a completed task."""
    return f"{DONE_TAG_PREFIX}/{task_id}"


def create_tag(name: str, message: str = "", cwd: Path | None = None) -> None:
    """Create an annotated git tag.

    Args:
        name: Tag name (e.g. 'pre-iter/task-001/0').
        message: Annotation message. Defaults to tag name.
        cwd: Directory to run from (should be a worktree).
    """
    _run("tag", "-a", name, "-m", message or name, cwd=cwd)
    logger.info("Created tag %s", name)


def tag_exists(name: str, cwd: Path | None = None) -> bool:
    """Return True if a tag with the given name exists."""
    result = _run("rev-parse", "--verify", f"refs/tags/{name}", cwd=cwd, check=False)
    return result.returncode == 0


def rollback_to_tag(tag_name: str, cwd: Path | None = None) -> None:
    """Hard-reset HEAD to the given tag.

    Aborts any in-progress merge, ensures on main, then resets.

    Args:
        tag_name: Tag to reset to.
        cwd: Directory to run from (should be a worktree).
    """
    _run("merge", "--abort", cwd=cwd, check=False)  # no-op if not merging
    ensure_on_main(cwd=cwd)
    _run("reset", "--hard", tag_name, cwd=cwd)
    logger.info("Rolled back to tag %s in %s", tag_name, cwd or "cwd")


def get_latest_tag(pattern: str, cwd: Path | None = None) -> str | None:
    """Return the most recent tag matching a glob pattern, or None.

    Args:
        pattern: Glob pattern (e.g. 'done/*').
        cwd: Directory to run from.
    """
    result = _run("tag", "-l", pattern, "--sort=-creatordate", cwd=cwd, check=False)
    tags = result.stdout.strip().splitlines()
    return tags[0] if tags else None


def cleanup_task_tags(task_id: str, cwd: Path | None = None) -> None:
    """Delete pre-iter tags for a completed task.

    Called after a done tag is created -- pre-iter checkpoints are
    no longer needed for rollback.

    Args:
        task_id: The completed task ID.
        cwd: Directory to run from.
    """
    pattern = f"{PRE_ITER_TAG_PREFIX}/{task_id}/*"
    result = _run("tag", "-l", pattern, cwd=cwd, check=False)
    for tag in result.stdout.strip().splitlines():
        if tag:
            _run("tag", "-d", tag, cwd=cwd, check=False)
    logger.info("Cleaned up pre-iter tags for %s", task_id)


# -- worktree health -------------------------------------------------------


def has_changes_since(ref: str, cwd: Path | None = None) -> bool:
    """Return True if HEAD has changes compared to the given ref.

    Args:
        ref: Git ref to compare against (tag, commit, branch).
        cwd: Directory to run from.
    """
    result = _run("diff", f"{ref}..HEAD", "--stat", cwd=cwd, check=False)
    return bool(result.stdout.strip())


def merge_from(source_branch: str, cwd: Path | None = None) -> bool:
    """Merge source_branch into the current branch.

    Args:
        source_branch: Branch to merge (e.g. 'ralph/task-001').
        cwd: Worktree directory (should be on main).

    Returns:
        True if merge succeeded, False on conflict.
    """
    result = _run("merge", source_branch, "--no-edit", cwd=cwd, check=False)
    if result.returncode != 0:
        logger.error("Merge of %s failed: %s", source_branch, result.stderr.strip())
        # Abort the failed merge to leave worktree clean
        _run("merge", "--abort", cwd=cwd, check=False)
        return False
    logger.info("Merged %s in %s", source_branch, cwd or "cwd")
    return True
