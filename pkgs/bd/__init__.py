"""Beads (`bd`) utilities.

Thin Python wrapper around the `bd` CLI from https://github.com/steveyegge/beads.

Main types:
    Issue: Dataclass representing a Beads issue
    IssueStatus: Issue status constants (OPEN, IN_PROGRESS, BLOCKED)

Functions:
    create_issue: Create a new issue via `bd create`
    get_issue: Get a single issue by ID via `bd show`
    list_issues: List all issues via `bd list`
    get_next_ready_issue: Get the next ready issue or None
    update_issue: Update issue fields via `bd update`
    close_issue: Mark issue as done via `bd close`
"""

from .main import (
    Issue,
    IssueStatus,
    close_issue,
    create_issue,
    get_issue,
    get_next_ready_issue,
    list_issues,
    update_issue,
)

__all__ = [
    "Issue",
    "IssueStatus",
    "close_issue",
    "create_issue",
    "get_issue",
    "get_next_ready_issue",
    "list_issues",
    "update_issue",
]
