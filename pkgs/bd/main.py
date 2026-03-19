"""Thin Python wrapper for the Beads (`bd`) CLI."""

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Self

logger = logging.getLogger(__name__)

BD_CMD = "bd"
BD_TIMEOUT = 30
DEFAULT_ISSUE_TYPE = "task"


class IssueStatus:
    """Issue status values used by Beads."""

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


def get_next_ready_issue() -> Issue | None:
    """Get the next open issue with no active blockers.

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

    return Issue.parse(issues[0])


def update_issue(
    issue_id: str,
    status: str | None = None,
    assignee: str | None = None,
) -> None:
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
    cmd = [BD_CMD, *args]
    logger.debug("Running: %s", " ".join(cmd))
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=BD_TIMEOUT
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


def _parse_dt(value: str | None) -> datetime | None:
    """Parse datetime string and return None if failed."""
    if not value:
        return
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return
