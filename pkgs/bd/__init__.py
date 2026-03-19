"""Beads (`bd`) utilities.

Thin Python wrapper around the `bd` CLI from https://github.com/steveyegge/beads.

Main types:
    Issue: Dataclass representing a Beads issue

Functions:
    get_next_ready_issue: Get the next ready issue or None
    update_issue: Update issue fields via `bd update`
    close_issue: Mark issue as done via `bd done`
"""

from .main import (
    Issue,
    close_issue,
    get_next_ready_issue,
    update_issue,
)

__all__ = [
    "Issue",
    "close_issue",
    "get_next_ready_issue",
    "update_issue",
]
