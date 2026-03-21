"""Thin Python wrapper for the Beads (`bd`) CLI."""

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Self

logger = logging.getLogger(__name__)

BD_CMD = "bd"
BD_TIMEOUT = 30
DEFAULT_ISSUE_TYPE = "task"


class IssueStatus(StrEnum):
    """Issue status values used by Beads.

    Inherits from StrEnum so values compare equal to plain strings
    (e.g. ``IssueStatus.OPEN == "open"``).
    """

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"


@dataclass
class Issue:
    """A Beads issue, matching the fields from `bd show --json`."""

    id: str
    title: str
    status: str = IssueStatus.OPEN
    priority: int = 2
    issue_type: str = DEFAULT_ISSUE_TYPE
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

    @classmethod
    def parse(cls, data: dict) -> Self:
        """Parse a JSON dict from bd CLI output into an Issue.

        Args:
            data: JSON dict from `bd show --json` or `bd ready --json`

        Returns:
            Parsed Issue instance with all fields populated
        """

        return cls(
            id=data["id"],
            title=data.get("title", ""),
            status=data.get("status", IssueStatus.OPEN),
            priority=data.get("priority", 2),
            issue_type=data.get("issue_type", DEFAULT_ISSUE_TYPE),
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


def get_next_ready_issue(*, cwd: Path | None = None) -> Issue | None:
    """Get the next open issue with no active blockers.

    Args:
        cwd: Working directory for the bd CLI (session-scoped).

    Returns:
        The first ready issue, or None if no ready issues exist.
    """
    result = _run_bd("ready", "--json", "--limit", "1", cwd=cwd)
    if result is None:
        return

    return _parse_first_issue(result.stdout)


def create_issue(
    title: str,
    *,
    description: str | None = None,
    acceptance: str | None = None,
    design: str | None = None,
    notes: str | None = None,
    assignee: str | None = None,
    priority: int | None = None,
    issue_type: str | None = None,
    labels: list[str] | None = None,
    parent: str | None = None,
    deps: list[str] | None = None,
    external_ref: str | None = None,
    cwd: Path | None = None,
) -> Issue:
    """Create a new Beads issue.

    Args:
        title: Issue title (required).
        cwd: Working directory for the bd CLI (session-scoped).
        **kwargs: Optional issue fields mapped to bd create flags.

    Returns:
        The created Issue.

    Raises:
        RuntimeError: If the bd create command fails.
    """
    args: list[str] = ["create", title, "--json"]
    _append_flag(args, "--description", description)
    _append_flag(args, "--acceptance", acceptance)
    _append_flag(args, "--design", design)
    _append_flag(args, "--notes", notes)
    _append_flag(args, "--assignee", assignee)
    _append_flag(args, "--priority", priority)
    _append_flag(args, "--type", issue_type)
    _append_flag(args, "--external-ref", external_ref)
    _append_flag(args, "--parent", parent)
    if labels is not None:
        args.extend(["--labels", ",".join(labels)])
    if deps is not None:
        args.extend(["--deps", ",".join(deps)])

    result = _run_bd(*args, cwd=cwd)
    if result is None:
        raise RuntimeError(f"Failed to create issue: {title}")

    data = json.loads(result.stdout.strip())
    issue = Issue.parse(data)
    logger.info("Created issue %s: %s", issue.id, issue.title)
    return issue


def list_issues(*, status: str | None = None, cwd: Path | None = None) -> list[Issue]:
    """List all Beads issues.

    Args:
        status: Optional status filter.
        cwd: Working directory for the bd CLI (session-scoped).

    Returns:
        List of Issues (empty list if none or on error).
    """
    args: list[str] = ["list", "--json"]
    _append_flag(args, "--status", status)

    result = _run_bd(*args, cwd=cwd)
    if result is None:
        return []

    stdout = result.stdout.strip()
    if not stdout:
        return []

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        logger.error("Failed to parse bd list output as JSON")
        return []

    items = data if isinstance(data, list) else [data]
    return [Issue.parse(item) for item in items]


def get_issue(issue_id: str, *, cwd: Path | None = None) -> Issue | None:
    """Get a single issue by ID.

    Args:
        issue_id: The issue ID (e.g., 'bd-123').
        cwd: Working directory for the bd CLI (session-scoped).

    Returns:
        The Issue, or None if not found.
    """
    result = _run_bd("show", issue_id, "--json", cwd=cwd)
    if result is None:
        return

    stdout = result.stdout.strip()
    if not stdout:
        return

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        logger.error("Failed to parse bd show output as JSON")
        return

    return Issue.parse(data)


def update_issue(
    issue_id: str,
    *,
    status: str | None = None,
    assignee: str | None = None,
    priority: int | None = None,
    description: str | None = None,
    acceptance: str | None = None,
    design: str | None = None,
    notes: str | None = None,
    append_notes: str | None = None,
    labels: list[str] | None = None,
    external_ref: str | None = None,
    cwd: Path | None = None,
) -> None:
    """Update an existing issue's fields.

    Only non-None arguments are sent to the bd CLI.

    Args:
        issue_id: The issue ID to update.
        cwd: Working directory for the bd CLI (session-scoped).
        **kwargs: Fields to update.

    Raises:
        RuntimeError: If the bd update command fails.
    """
    args: list[str] = ["update", issue_id]
    _append_flag(args, "--status", status)
    _append_flag(args, "--assignee", assignee)
    _append_flag(args, "--priority", priority)
    _append_flag(args, "--description", description)
    _append_flag(args, "--acceptance", acceptance)
    _append_flag(args, "--design", design)
    _append_flag(args, "--notes", notes)
    _append_flag(args, "--append-notes", append_notes)
    _append_flag(args, "--external-ref", external_ref)
    if labels is not None:
        args.extend(["--labels", ",".join(labels)])

    result = _run_bd(*args, cwd=cwd)
    if result is None:
        raise RuntimeError(f"Failed to update issue {issue_id}")
    logger.info("Updated issue %s", issue_id)


def close_issue(issue_id: str, *, cwd: Path | None = None) -> None:
    """Mark an issue as done.

    Args:
        issue_id: The issue ID to close.
        cwd: Working directory for the bd CLI (session-scoped).

    Raises:
        RuntimeError: If the bd close command fails.
    """
    result = _run_bd("close", issue_id, cwd=cwd)
    if result is None:
        raise RuntimeError(f"Failed to mark issue {issue_id} as done")
    logger.info("Marked issue %s as done", issue_id)


# -- internal helpers ---------------------------------------------------------


def _run_bd(
    *args: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str] | None:
    """Run a bd CLI command and return the result.

    Args:
        *args: Arguments to pass to the bd command.
        cwd: Working directory for subprocess.

    Returns:
        CompletedProcess if successful, None if command fails or times out.
    """
    cmd = [BD_CMD, *args]
    logger.debug("Running: %s", " ".join(cmd))
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=BD_TIMEOUT,
            cwd=cwd,
        )
    except FileNotFoundError:
        logger.error("bd CLI not found; is beads installed?")
        return
    except subprocess.TimeoutExpired:
        logger.error("bd %s timed out after %ss", args[0] if args else "?", BD_TIMEOUT)
        return
    except subprocess.CalledProcessError as e:
        logger.error("bd %s failed: %s", args[0] if args else "?", e.stderr.strip())
        return


def _append_flag(args: list[str], flag: str, value) -> None:
    """Append --flag value to args if value is not None."""
    if value is not None:
        args.extend([flag, str(value)])


def _parse_first_issue(stdout: str) -> Issue | None:
    """Parse the first issue from bd JSON output (list or single object)."""
    stdout = stdout.strip()
    if not stdout:
        return

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        logger.error("Failed to parse bd output as JSON")
        return

    issues = data if isinstance(data, list) else [data]
    if not issues:
        return

    return Issue.parse(issues[0])


def _parse_dt(value: str | None) -> datetime | None:
    """Parse datetime string and return None if failed."""
    if not value:
        return
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return
