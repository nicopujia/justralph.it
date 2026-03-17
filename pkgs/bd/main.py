"""Beads (`bd`) utilities.

Thin Python wrapper around the `bd` CLI from https://github.com/steveyegge/beads.
"""

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Issue:
    """A Beads issue, matching the core fields from `bd show --json`."""

    id: str
    title: str
    status: str = "open"
    priority: int = 2
    issue_type: str = "task"
    description: str = ""
    assignee: str = ""
    labels: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


def _parse_issue(data: dict) -> Issue:
    """Parse a JSON dict from bd CLI output into an Issue."""

    def _parse_dt(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return None

    return Issue(
        id=data["id"],
        title=data.get("title", ""),
        status=data.get("status", "open"),
        priority=data.get("priority", 2),
        issue_type=data.get("issue_type", "task"),
        description=data.get("description", ""),
        assignee=data.get("assignee", ""),
        labels=data.get("labels") or [],
        created_at=_parse_dt(data.get("created_at")),
        updated_at=_parse_dt(data.get("updated_at")),
    )


def get_next_ready_issue(timeout: float | None = None) -> Issue | None:
    """Get the next ready issue (open, no active blockers) from Beads.

    Calls `bd ready --json --limit 1` and parses the first result.
    Returns None if no ready issues exist or if bd is not configured.
    """
    result = _run_bd("ready", "--json", "--limit", "1", timeout=timeout)
    if result is None:
        return None

    stdout = result.stdout.strip()
    if not stdout:
        return None

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        logger.error("Failed to parse bd ready output as JSON")
        return None

    # bd ready --json returns a list of issues
    issues = data if isinstance(data, list) else [data]
    if not issues:
        return None

    return _parse_issue(issues[0])


class StopRequested(Exception):
    """Raised when a stop file is detected during polling."""


class RestartRequested(Exception):
    """Raised when a restart file is detected during polling."""


def wait_for_next_ready_issue(
    poll_interval: float,
    stop_file: Path,
    restart_file: Path,
    timeout: float | None = None,
) -> Issue:
    """Block until a ready issue appears, then return it.

    Polls `bd ready` every *poll_interval* seconds.
    Raises StopRequested if the stop file appears while waiting.
    Raises RestartRequested if the restart file appears while waiting.
    """
    logger.info("Waiting for a ready issue (polling every %ss)...", poll_interval)
    while True:
        if stop_file.exists():
            reason = stop_file.read_text() or "found empty stop file"
            stop_file.unlink()
            raise StopRequested(reason)

        if restart_file.exists():
            reason = restart_file.read_text() or "found empty restart file"
            restart_file.unlink()
            raise RestartRequested(reason)

        issue = get_next_ready_issue(timeout=timeout)
        if issue is not None:
            logger.info("Found ready issue: %s", issue.id)
            return issue
        time.sleep(poll_interval)


def update_issue(
    issue_id: str,
    status: str | None = None,
    assignee: str | None = None,
    timeout: float | None = None,
) -> None:
    """Update an issue's fields.

    Raises:
        RuntimeError: If bd update fails.
    """
    args = ["update", issue_id]
    if status:
        args.extend(["--status", status])
    if assignee:
        args.extend(["--assignee", assignee])
    result = _run_bd(*args, timeout=timeout)
    if result is None:
        raise RuntimeError(f"Failed to update issue {issue_id}")
    logger.info("Updated issue %s (status=%s, assignee=%s)", issue_id, status, assignee)


def _run_bd(
    *args: str, timeout: float | None = None
) -> subprocess.CompletedProcess[str] | None:
    """Run a bd CLI command and return the result, or None on failure."""
    cmd = ["bd", *args]
    logger.debug("Running: %s", " ".join(cmd))
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=timeout
        )
    except FileNotFoundError:
        logger.error("bd CLI not found; is beads installed?")
        return None
    except subprocess.TimeoutExpired:
        logger.error("bd %s timed out after %ss", args[0] if args else "?", timeout)
        return None
    except subprocess.CalledProcessError as e:
        logger.error("bd %s failed: %s", args[0] if args else "?", e.stderr.strip())
        return None
