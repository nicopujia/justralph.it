"""YAML-backed task store for Ralph.

Replaces the old Beads (bd) CLI wrapper with a local YAML file. No external
binary required -- all CRUD operations read/write ``tasks.yaml`` directly.
"""

import fcntl
import logging
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Self

import yaml

logger = logging.getLogger(__name__)

TASKS_FILE = "tasks.yaml"
DEFAULT_PRIORITY = 2


class TaskStatus(StrEnum):
    """Task lifecycle states.

    Inherits from StrEnum so ``TaskStatus.OPEN == "open"`` works.
    """

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


@dataclass
class Task:
    """A single work item stored in tasks.yaml."""

    id: str
    title: str
    status: str = TaskStatus.OPEN
    priority: int = DEFAULT_PRIORITY
    body: str = ""
    assignee: str = ""
    labels: list[str] = field(default_factory=list)
    parent: str = ""
    parallel_group: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def as_xml(self) -> str:
        """Serialize to XML for injection into agent prompts.

        Empty/None fields are omitted.
        """
        lines: list[str] = ["<Task>"]
        for f in self.__dataclass_fields__:
            value = getattr(self, f)
            if value is None or value == "" or value == [] or value == 0:
                continue
            tag = f.replace("_", " ").title().replace(" ", "")
            if isinstance(value, list):
                inner = "".join(f"<Item>{v}</Item>" for v in value)
                lines.append(f"  <{tag}>{inner}</{tag}>")
            elif isinstance(value, datetime):
                lines.append(f"  <{tag}>{value.isoformat()}</{tag}>")
            else:
                lines.append(f"  <{tag}>{value}</{tag}>")
        lines.append("</Task>")
        return "\n".join(lines)

    @classmethod
    def parse(cls, data: dict) -> Self:
        """Build a Task from a YAML dict.

        Reconciles ralphy's ``completed: true`` with our ``status`` field.
        """
        status = data.get("status", TaskStatus.OPEN)
        # If ralphy set completed=true but our status wasn't updated, sync it
        if data.get("completed") is True and status != TaskStatus.DONE:
            status = TaskStatus.DONE
        return cls(
            id=data["id"],
            title=data.get("title", ""),
            status=status,
            priority=data.get("priority", DEFAULT_PRIORITY),
            body=data.get("body", ""),
            assignee=data.get("assignee", ""),
            labels=data.get("labels") or [],
            parent=data.get("parent", ""),
            parallel_group=data.get("parallel_group", 0),
            created_at=_parse_dt(data.get("created_at")),
            updated_at=_parse_dt(data.get("updated_at")),
        )

    def to_dict(self) -> dict:
        """Serialize for YAML output. Includes `completed` for ralphy compat."""
        d: dict = {
            "id": self.id,
            "title": self.title,
            "status": str(self.status),
            "priority": self.priority,
            "completed": self.status == TaskStatus.DONE,
        }
        if self.parallel_group:
            d["parallel_group"] = self.parallel_group
        if self.body:
            d["body"] = self.body
        if self.assignee:
            d["assignee"] = self.assignee
        if self.labels:
            d["labels"] = self.labels
        if self.parent:
            d["parent"] = self.parent
        if self.created_at:
            d["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            d["updated_at"] = self.updated_at.isoformat()
        return d


# -- public CRUD -------------------------------------------------------------


def create_task(
    title: str,
    *,
    body: str | None = None,
    priority: int | None = None,
    assignee: str | None = None,
    labels: list[str] | None = None,
    parent: str | None = None,
    parallel_group: int | None = None,
    cwd: Path | None = None,
) -> Task:
    """Create a new task and persist it to tasks.yaml.

    Returns the created Task.
    Raises RuntimeError if the write fails.
    """
    data = _load_tasks(cwd)
    tasks = data.get("tasks", [])
    now = datetime.now(timezone.utc)
    task = Task(
        id=_next_id(tasks),
        title=title,
        body=body or "",
        priority=priority if priority is not None else DEFAULT_PRIORITY,
        assignee=assignee or "",
        labels=labels or [],
        parent=parent or "",
        parallel_group=parallel_group or 0,
        created_at=now,
        updated_at=now,
    )
    tasks.append(task.to_dict())
    data["tasks"] = tasks
    _save_tasks(data, cwd)
    logger.info("Created task %s: %s", task.id, task.title)
    return task


def get_task(task_id: str, *, cwd: Path | None = None) -> Task | None:
    """Return a single task by ID, or None if not found."""
    for item in _load_tasks(cwd).get("tasks", []):
        if item.get("id") == task_id:
            return Task.parse(item)
    return None


def list_tasks(*, status: str | None = None, cwd: Path | None = None) -> list[Task]:
    """List all tasks, optionally filtered by status."""
    items = _load_tasks(cwd).get("tasks", [])
    tasks = [Task.parse(item) for item in items]
    if status is not None:
        tasks = [t for t in tasks if t.status == status]
    return tasks


def update_task(
    task_id: str,
    *,
    status: str | None = None,
    assignee: str | None = None,
    body: str | None = None,
    priority: int | None = None,
    labels: list[str] | None = None,
    append_notes: str | None = None,
    cwd: Path | None = None,
) -> None:
    """Update fields on an existing task.

    Only non-None arguments are written. Raises RuntimeError if not found.
    """
    data = _load_tasks(cwd)
    tasks = data.get("tasks", [])
    for item in tasks:
        if item.get("id") != task_id:
            continue
        if status is not None:
            item["status"] = str(status)
        if assignee is not None:
            item["assignee"] = assignee
        if body is not None:
            item["body"] = body
        if priority is not None:
            item["priority"] = priority
        if labels is not None:
            item["labels"] = labels
        if append_notes is not None:
            existing = item.get("body", "")
            sep = "\n" if existing else ""
            item["body"] = existing + sep + append_notes
        item["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_tasks(data, cwd)
        logger.info("Updated task %s", task_id)
        return
    raise RuntimeError(f"Task {task_id} not found")


def close_task(task_id: str, *, cwd: Path | None = None) -> None:
    """Mark a task as done. Raises RuntimeError if not found."""
    update_task(task_id, status=TaskStatus.DONE, cwd=cwd)
    logger.info("Marked task %s as done", task_id)


def get_next_ready_task(*, cwd: Path | None = None) -> Task | None:
    """Return the highest-priority OPEN task whose parent (if any) is DONE.

    Tasks with no parent are always eligible. Among eligible tasks, the
    lowest priority number (highest urgency) wins.
    """
    all_tasks = list_tasks(cwd=cwd)
    done_ids = {t.id for t in all_tasks if t.status == TaskStatus.DONE}

    ready = []
    for t in all_tasks:
        if t.status != TaskStatus.OPEN:
            continue
        if t.parent and t.parent not in done_ids:
            continue
        ready.append(t)

    if not ready:
        return None
    ready.sort(key=lambda t: t.priority)
    return ready[0]


def compute_parallel_groups(*, cwd: Path | None = None) -> None:
    """Assign parallel_group values based on the task dependency graph.

    Tasks with no parent (or parent already done) get group 1.
    Tasks whose parent is in group N get group N+1.
    Writes the updated groups back to tasks.yaml.
    """
    data = _load_tasks(cwd)
    items = data.get("tasks", [])
    if not items:
        return

    # Build lookup: id -> item and id -> group
    by_id: dict[str, dict] = {item["id"]: item for item in items if "id" in item}
    groups: dict[str, int] = {}

    def _group_of(task_id: str) -> int:
        if task_id in groups:
            return groups[task_id]
        item = by_id.get(task_id)
        if not item:
            return 1
        parent = item.get("parent", "")
        if not parent or parent not in by_id:
            groups[task_id] = 1
            return 1
        # Parent's group + 1
        pg = _group_of(parent)
        groups[task_id] = pg + 1
        return pg + 1

    changed = False
    for item in items:
        tid = item.get("id", "")
        if not tid:
            continue
        new_group = _group_of(tid)
        if item.get("parallel_group") != new_group:
            item["parallel_group"] = new_group
            changed = True

    if changed:
        _save_tasks(data, cwd)
        logger.info("Computed parallel groups for %d tasks", len(items))


def reconcile_completed(*, cwd: Path | None = None) -> None:
    """Sync ralphy's ``completed: true`` back to ``status: done``.

    Called after a ralphy run to reconcile state. Also ensures
    ``completed`` stays in sync with ``status`` for tasks we closed.
    """
    data = _load_tasks(cwd)
    changed = False
    for item in data.get("tasks", []):
        completed = item.get("completed")
        status = item.get("status", "open")
        if completed is True and status != "done":
            item["status"] = "done"
            changed = True
        elif status == "done" and completed is not True:
            item["completed"] = True
            changed = True
    if changed:
        _save_tasks(data, cwd)
        logger.info("Reconciled completed/status fields")


# -- internal helpers ---------------------------------------------------------


def _tasks_path(cwd: Path | None) -> Path:
    """Resolve the tasks.yaml path."""
    base = cwd or Path.cwd()
    return base / TASKS_FILE


def _load_tasks(cwd: Path | None) -> dict:
    """Read tasks.yaml, returning an empty structure if missing."""
    path = _tasks_path(cwd)
    if not path.exists():
        return {"tasks": []}
    with open(path) as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            data = yaml.safe_load(f)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return data if isinstance(data, dict) else {"tasks": []}


def _save_tasks(data: dict, cwd: Path | None) -> None:
    """Atomically write tasks.yaml (write to temp, then rename)."""
    path = _tasks_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".yaml")
    try:
        with open(fd, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        Path(tmp).rename(path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def _next_id(tasks: list[dict]) -> str:
    """Generate the next sequential task ID (task-001, task-002, ...)."""
    max_num = 0
    for t in tasks:
        tid = t.get("id", "")
        if tid.startswith("task-"):
            try:
                num = int(tid[5:])
                max_num = max(max_num, num)
            except ValueError:
                pass
    return f"task-{max_num + 1:03d}"


def _parse_dt(value: str | None) -> datetime | None:
    """Parse ISO datetime, returning None on failure."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None
