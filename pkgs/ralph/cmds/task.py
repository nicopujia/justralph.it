"""CLI for task CRUD operations (ralph task create/list/show/update/close)."""

import argparse
import json
import sys
from dataclasses import dataclass, field

import tasks

from ..config import Config
from . import Command


@dataclass
class TaskConfig(Config):
    """Config for the task command. Fields populated by sub-parsers."""

    # Sub-parser populates these; all have defaults so missing keys are fine.
    action: str = field(default="", metadata={"help": "Action", "cli": False})
    title: str = field(default="", metadata={"help": "Task title", "cli": False})
    task_id: str = field(default="", metadata={"help": "Task ID", "cli": False})
    body: str | None = field(default=None, metadata={"help": "Task body", "cli": False})
    priority: int | None = field(default=None, metadata={"help": "Priority (0-4)", "cli": False})
    assignee: str | None = field(default=None, metadata={"help": "Assignee", "cli": False})
    labels: str | None = field(default=None, metadata={"help": "Labels (comma-separated)", "cli": False})
    parent: str | None = field(default=None, metadata={"help": "Parent task ID", "cli": False})
    task_status: str | None = field(default=None, metadata={"help": "Status filter/value", "cli": False})
    append_notes: str | None = field(default=None, metadata={"help": "Append to body", "cli": False})
    parallel_group: int | None = field(default=None, metadata={"help": "Parallel batch group", "cli": False})
    output_json: bool = field(default=False, metadata={"help": "JSON output", "cli": False})


class Task(Command):
    help = "Task CRUD: create, list, show, update, close"
    config = TaskConfig

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        sub = parser.add_subparsers(dest="action")

        # create
        p_create = sub.add_parser("create", help="Create a new task")
        p_create.add_argument("title", help="Task title")
        p_create.add_argument("--body", help="Task body/description")
        p_create.add_argument("--priority", type=int, help="Priority (0=highest, 4=lowest)")
        p_create.add_argument("--assignee", help="Assignee name")
        p_create.add_argument("--labels", help="Labels (comma-separated)")
        p_create.add_argument("--parent", help="Parent task ID")
        p_create.add_argument("--parallel-group", type=int, dest="parallel_group", help="Parallel batch group (0=sequential)")
        p_create.add_argument("--json", dest="output_json", action="store_true")

        # list
        p_list = sub.add_parser("list", help="List tasks")
        p_list.add_argument("--status", dest="task_status", help="Filter by status")
        p_list.add_argument("--json", dest="output_json", action="store_true")

        # show
        p_show = sub.add_parser("show", help="Show a single task")
        p_show.add_argument("task_id", help="Task ID")
        p_show.add_argument("--json", dest="output_json", action="store_true")

        # update
        p_update = sub.add_parser("update", help="Update a task")
        p_update.add_argument("task_id", help="Task ID")
        p_update.add_argument("--status", dest="task_status", help="New status")
        p_update.add_argument("--body", help="New body")
        p_update.add_argument("--priority", type=int, help="New priority")
        p_update.add_argument("--assignee", help="New assignee")
        p_update.add_argument("--labels", help="New labels (comma-separated)")
        p_update.add_argument("--append-notes", dest="append_notes", help="Append to body")
        p_update.add_argument("--parallel-group", type=int, dest="parallel_group", help="Parallel batch group")

        # close
        p_close = sub.add_parser("close", help="Mark task as done")
        p_close.add_argument("task_id", help="Task ID")

    def run(self) -> None:
        cfg: TaskConfig = self.cfg  # type: ignore[assignment]
        cwd = cfg.base_dir

        match cfg.action:
            case "create":
                labels = cfg.labels.split(",") if cfg.labels else None
                task = tasks.create_task(
                    cfg.title,
                    body=cfg.body,
                    priority=cfg.priority,
                    assignee=cfg.assignee,
                    labels=labels,
                    parent=cfg.parent,
                    parallel_group=cfg.parallel_group,
                    cwd=cwd,
                )
                if cfg.output_json:
                    print(json.dumps(task.to_dict(), indent=2))
                else:
                    print(f"Created {task.id}: {task.title}")

            case "list":
                task_list = tasks.list_tasks(status=cfg.task_status, cwd=cwd)
                if cfg.output_json:
                    print(json.dumps([t.to_dict() for t in task_list], indent=2))
                else:
                    if not task_list:
                        print("No tasks found.")
                        return
                    for t in task_list:
                        mark = "x" if t.status == tasks.TaskStatus.DONE else " "
                        print(f"[{mark}] {t.id}  {t.title}  ({t.status})")

            case "show":
                task = tasks.get_task(cfg.task_id, cwd=cwd)
                if task is None:
                    print(f"Task {cfg.task_id} not found.", file=sys.stderr)
                    raise SystemExit(1)
                if cfg.output_json:
                    print(json.dumps(task.to_dict(), indent=2))
                else:
                    print(f"ID:       {task.id}")
                    print(f"Title:    {task.title}")
                    print(f"Status:   {task.status}")
                    print(f"Priority: {task.priority}")
                    if task.assignee:
                        print(f"Assignee: {task.assignee}")
                    if task.labels:
                        print(f"Labels:   {', '.join(task.labels)}")
                    if task.parent:
                        print(f"Parent:   {task.parent}")
                    if task.body:
                        print(f"\n{task.body}")

            case "update":
                labels = cfg.labels.split(",") if cfg.labels else None
                tasks.update_task(
                    cfg.task_id,
                    status=cfg.task_status,
                    body=cfg.body,
                    priority=cfg.priority,
                    assignee=cfg.assignee,
                    labels=labels,
                    append_notes=cfg.append_notes,
                    cwd=cwd,
                )
                print(f"Updated {cfg.task_id}")

            case "close":
                tasks.close_task(cfg.task_id, cwd=cwd)
                print(f"Closed {cfg.task_id}")

            case _:
                print("Usage: ralph task {create,list,show,update,close}", file=sys.stderr)
                raise SystemExit(1)
