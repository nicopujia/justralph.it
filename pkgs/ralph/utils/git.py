"""Git utilities for branch and repo management."""

import logging
import subprocess
from pathlib import Path

from ..config import BRANCH_PREFIX, MAIN_BRANCH, RALPH_DIR_NAME

logger = logging.getLogger(__name__)

BARE_HEAD_REF = "refs/heads/_bare"
GIT_BARE_CONFIG_KEY = "core.bare"
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


def is_bare(path: Path) -> bool:
    """Return True if the repo at *path* is bare."""
    result = _run("config", "--get", GIT_BARE_CONFIG_KEY, cwd=path, check=False)
    return result.stdout.strip().lower() == "true"


def init_bare(path: Path) -> None:
    """Create a bare repo at *path/.git* with an initial empty commit.

    After this call the repo is bare, has a single ``main`` branch with
    one empty commit, and HEAD points to a placeholder ref so that no
    branch is "checked out" at the root (allowing worktrees to own them).
    """
    path.mkdir(parents=True, exist_ok=True)
    _run("init", cwd=path)
    _run("commit", "--allow-empty", "-m", INITIAL_COMMIT_MSG, cwd=path)
    _run("branch", "-M", MAIN_BRANCH, cwd=path)
    _run("config", GIT_BARE_CONFIG_KEY, "true", cwd=path)
    _run("symbolic-ref", "HEAD", BARE_HEAD_REF, cwd=path)
    logger.info("Initialized bare repo at %s", path)


def convert_to_bare(path: Path) -> None:
    """Convert an existing (non-bare) repo at *path* to bare.

    Tracked files in the root working tree are removed so that worktrees
    become the only working copies.
    """
    _run("config", GIT_BARE_CONFIG_KEY, "true", cwd=path)
    _run("symbolic-ref", "HEAD", BARE_HEAD_REF, cwd=path)

    # Remove tracked files left over from the old working tree
    result = _run("ls-files", cwd=path, check=False)
    for name in result.stdout.splitlines():
        f = path / name
        if f.is_file():
            f.unlink()
    # Remove now-empty directories (excluding .git, .ralph, worktrees)
    _prune_empty_dirs(path, keep={".git", RALPH_DIR_NAME})
    logger.info("Converted %s to bare repo", path)


def add_worktree(repo: Path, name: str, branch: str, new_branch: bool = False) -> Path:
    """Add a worktree at *repo/name* on *branch*.

    Args:
        repo: Root of the bare repo.
        name: Subdirectory name for the worktree.
        branch: Branch to check out (or create if *new_branch*).
        new_branch: If True, create *branch* from the current HEAD.

    Returns:
        Path to the new worktree directory.
    """
    wt_path = repo / name
    if new_branch:
        _run("worktree", "add", "-b", branch, str(wt_path), MAIN_BRANCH, cwd=repo)
    else:
        _run("worktree", "add", str(wt_path), branch, cwd=repo)
    logger.info("Added worktree %s on branch %s", wt_path, branch)
    return wt_path


def has_worktree(repo: Path, name: str) -> bool:
    """Return True if a worktree named *name* already exists."""
    result = _run("worktree", "list", "--porcelain", cwd=repo, check=False)
    target = str((repo / name).resolve())
    for line in result.stdout.splitlines():
        if line.startswith("worktree ") and line.split(" ", 1)[1] == target:
            return True
    return False


def reset_branch(repo: Path, branch: str, target: str) -> None:
    """Reset *branch* to point at the same commit as *target*.

    Useful for syncing a worktree branch (e.g. dev) with another (e.g. main)
    without checking it out.

    Args:
        repo: Root of the bare repo.
        branch: Branch to reset.
        target: Branch or ref to reset *branch* to.
    """
    _run("branch", "-f", branch, target, cwd=repo)
    logger.info("Reset branch %s to %s", branch, target)


def _prune_empty_dirs(root: Path, keep: set[str]) -> None:
    """Remove empty directories under *root*, skipping *keep* names."""
    for d in sorted(root.rglob("*"), reverse=True):
        if not d.is_dir():
            continue
        if d.name in keep or any(p.name in keep for p in d.relative_to(root).parents):
            continue
        try:
            d.rmdir()  # only succeeds if empty
        except OSError:
            pass


def cleanup_branch(issue_id: str) -> None:
    """Delete the ralph/[issue-id] branch if it exists.

    Args:
        issue_id: The issue ID (e.g., 'bd-123')
    """
    branch_name = f"{BRANCH_PREFIX}{issue_id}"
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

        if current_branch != MAIN_BRANCH:
            logger.info("Currently on branch %s; checking out main", current_branch)
            subprocess.run(
                ["git", "checkout", MAIN_BRANCH],
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


def reset_git_state(issue_id: str) -> None:
    """Reset git state: ensure on main and delete issue branch.

    Args:
        issue_id: The issue ID (e.g., 'bd-123')
    """
    ensure_on_main()
    cleanup_branch(issue_id)
