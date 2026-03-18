"""Python wrapper for the Beads (`bd`) CLI.

Provides dataclasses and functions for interacting with Beads issues,
including querying ready issues, updating status, and polling for new work.
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
    """A Beads issue, matching the fields from `bd show --json`."""

    id: str
    title: str
    status: str = "open"
    priority: int = 2
    issue_type: str = "task"
    description: str = ""
    acceptance: str = ""
    design: str = ""
    notes: str = ""
    assignee: str = ""
    labels: list[str] = field(default_factory=list)
    estimate: int = 0
    external_ref: str = ""
    parent: str = ""
    spec_id: str = ""
    due: datetime | None = None
    defer: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict = field(default_factory=dict)

    def as_xml(self) -> str:
        """Return the issue as an XML string with Capitalized tags.

        Fields that are not set (empty string, empty list, empty dict,
        zero for estimate, or None) are skipped.
        """
        lines: list[str] = ["<Issue>"]
        for f in self.__dataclass_fields__:
            value = getattr(self, f)
            # Skip unset / default-empty values
            if value is None or value == "" or value == [] or value == {} or value == 0:
                continue
            tag = f.replace("_", " ").title().replace(" ", "")
            if isinstance(value, list):
                inner = "".join(f"<Item>{v}</Item>" for v in value)
                lines.append(f"  <{tag}>{inner}</{tag}>")
            elif isinstance(value, dict):
                inner = "".join(f"<{k}>{v}</{k}>" for k, v in value.items())
                lines.append(f"  <{tag}>{inner}</{tag}>")
            elif isinstance(value, datetime):
                lines.append(f"  <{tag}>{value.isoformat()}</{tag}>")
            else:
                lines.append(f"  <{tag}>{value}</{tag}>")
        lines.append("</Issue>")
        return "\n".join(lines)


def _parse_issue(data: dict) -> Issue:
    """Parse a JSON dict from bd CLI output into an Issue.

    Args:
        data: Raw JSON dict from `bd show --json` or `bd ready --json`

    Returns:
        Parsed Issue instance with all fields populated
    """

    def _parse_dt(value: str | None) -> datetime | None:
        if not value:
            return
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return

    return Issue(
        id=data["id"],
        title=data.get("title", ""),
        status=data.get("status", "open"),
        priority=data.get("priority", 2),
        issue_type=data.get("issue_type", "task"),
        description=data.get("description", ""),
        acceptance=data.get("acceptance", ""),
        design=data.get("design", ""),
        notes=data.get("notes", ""),
        assignee=data.get("assignee", ""),
        labels=data.get("labels") or [],
        estimate=data.get("estimate", 0),
        external_ref=data.get("external_ref", ""),
        parent=data.get("parent", ""),
        spec_id=data.get("spec_id", ""),
        due=_parse_dt(data.get("due")),
        defer=_parse_dt(data.get("defer")),
        created_at=_parse_dt(data.get("created_at")),
        updated_at=_parse_dt(data.get("updated_at")),
        metadata=data.get("metadata") or {},
    )


def get_next_ready_issue() -> Issue | None:
    """Get the next ready issue (open, no active blockers) from Beads.

    Calls `bd ready --json --limit 1` and parses the first result.

    Returns:
        The first ready issue, or None if no ready issues exist
    """
    result = _run_bd("ready", "--json", "--limit", "1")
    if result is None:
        return

    stdout = result.stdout.strip()
    if not stdout:
        return

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        logger.error("Failed to parse bd ready output as JSON")
        return

    # bd ready --json returns a list of issues
    issues = data if isinstance(data, list) else [data]
    if not issues:
        return

    return _parse_issue(issues[0])


class StopRequested(Exception):
    """Raised when a stop file is detected during polling."""


class RestartRequested(Exception):
    """Raised when a restart file is detected during polling."""


def wait_for_next_ready_issue(
    poll_interval: float,
    stop_file: Path,
    restart_file: Path,
) -> Issue:
    """Block until a ready issue appears, then return it.

    Polls `bd ready` every poll_interval seconds and checks for signal files.

    Args:
        poll_interval: Seconds to wait between polls
        stop_file: Path to stop signal file
        restart_file: Path to restart signal file

    Returns:
        The first ready issue found

    Raises:
        StopRequested: If stop file appears while waiting
        RestartRequested: If restart file appears while waiting
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

        issue = get_next_ready_issue()
        if issue is not None:
            logger.info("Found ready issue: %s", issue.id)
            return issue
        time.sleep(poll_interval)


def update_issue(
    issue_id: str,
    status: str | None = None,
    assignee: str | None = None,
) -> None:
    """Update an issue's status and/or assignee fields.

    Args:
        issue_id: The issue ID (e.g., 'bd-123')
        status: New status value (e.g., 'open', 'in_progress', 'blocked')
        assignee: New assignee value

    Raises:
        RuntimeError: If bd update command fails
    """
    args = ["update", issue_id]
    if status:
        args.extend(["--status", status])
    if assignee:
        args.extend(["--assignee", assignee])
    result = _run_bd(*args)
    if result is None:
        raise RuntimeError(f"Failed to update issue {issue_id}")
    logger.info("Updated issue %s (status=%s, assignee=%s)", issue_id, status, assignee)


def close_issue(issue_id: str) -> None:
    """Mark an issue as closed/done.

    Args:
        issue_id: The issue ID (e.g., 'bd-123')

    Raises:
        RuntimeError: If bd close command fails
    """
    result = _run_bd("close", issue_id)
    if result is None:
        raise RuntimeError(f"Failed to mark issue {issue_id} as done")
    logger.info("Marked issue %s as done", issue_id)


def _run_bd(*args: str) -> subprocess.CompletedProcess[str] | None:
    """Run a bd CLI command and return the result.

    Args:
        *args: Arguments to pass to the bd command

    Returns:
        CompletedProcess if successful, None if command fails or times out
    """
    timeout = 30
    cmd = ["bd", *args]
    logger.debug("Running: %s", " ".join(cmd))
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=timeout
        )
    except FileNotFoundError:
        logger.error("bd CLI not found; is beads installed?")
        return
    except subprocess.TimeoutExpired:
        logger.error("bd %s timed out after %ss", args[0] if args else "?", timeout)
        return
    except subprocess.CalledProcessError as e:
        logger.error("bd %s failed: %s", args[0] if args else "?", e.stderr.strip())
        return
