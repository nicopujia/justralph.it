"""Beads (`bd`) utilities.

Thin Python wrapper around the `bd` CLI from https://github.com/steveyegge/beads.

Main types:
    Issue: Dataclass representing a Beads issue

Exceptions:
    StopRequested: Raised when stop signal file detected while waiting
    RestartRequested: Raised when restart signal file detected while waiting

Functions:
    get_next_ready_issue: Get the next ready issue or None
    wait_for_next_ready_issue: Poll for issues, raises on signal files
    update_issue: Update issue fields via `bd update`
    close_issue: Mark issue as done via `bd done`
"""

from .main import (
    Issue,
    RestartRequested,
    StopRequested,
    close_issue,
    get_next_ready_issue,
    update_issue,
    wait_for_next_ready_issue,
)

__all__ = [
    "Issue",
    "RestartRequested",
    "StopRequested",
    "close_issue",
    "get_next_ready_issue",
    "update_issue",
    "wait_for_next_ready_issue",
]
