"""Edge case tests for reconcile_completed() in tasks.main.

Complements the 4 basic tests in test_task_store.py with deeper scenarios:
mixed batches, missing keys, non-bool completed values, and status transitions.
"""

from pathlib import Path
import time

import yaml

from tasks.main import reconcile_completed


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _write(tasks_dir: Path, tasks: list[dict]) -> None:
    """Write raw task dicts to tasks.yaml, bypassing create_task."""
    (tasks_dir / "tasks.yaml").write_text(yaml.dump({"tasks": tasks}))


def _read(tasks_dir: Path) -> list[dict]:
    """Return raw task dicts from tasks.yaml."""
    return yaml.safe_load((tasks_dir / "tasks.yaml").read_text())["tasks"]


# ---------------------------------------------------------------------------
# 1. mixed batch: all three sync cases in one call
# ---------------------------------------------------------------------------


def test_multiple_tasks_mixed_sync(tasks_dir: Path):
    """Three tasks covering all three sync states; one call reconciles all."""
    _write(tasks_dir, [
        # needs completed->status sync
        {"id": "task-001", "title": "A", "status": "open",   "completed": True},
        # needs status->completed sync
        {"id": "task-002", "title": "B", "status": "done",   "completed": False},
        # already synced -- no change needed
        {"id": "task-003", "title": "C", "status": "open",   "completed": False},
    ])
    reconcile_completed(cwd=tasks_dir)
    items = _read(tasks_dir)
    by_id = {t["id"]: t for t in items}

    # task-001: completed=True wins, status must become done
    assert by_id["task-001"]["status"] == "done"
    # task-002: status=done wins, completed must become True
    assert by_id["task-002"]["completed"] is True
    # task-003: unchanged
    assert by_id["task-003"]["status"] == "open"
    assert by_id["task-003"]["completed"] is False


# ---------------------------------------------------------------------------
# 2. completed key absent entirely -- status=done adds completed=True
# ---------------------------------------------------------------------------


def test_completed_missing_key_with_status_done(tasks_dir: Path):
    """No 'completed' key + status=done -> completed=True is added."""
    # dict has no "completed" key
    _write(tasks_dir, [{"id": "task-001", "title": "X", "status": "done"}])
    reconcile_completed(cwd=tasks_dir)
    items = _read(tasks_dir)
    assert items[0]["completed"] is True


def test_completed_missing_key_with_status_open(tasks_dir: Path):
    """No 'completed' key + status=open -> completed=True is NOT added."""
    _write(tasks_dir, [{"id": "task-001", "title": "X", "status": "open"}])
    reconcile_completed(cwd=tasks_dir)
    items = _read(tasks_dir)
    # open tasks should not gain a 'completed' key (no branch triggers for open + missing)
    # The elif only fires when status == "done", so nothing changes here
    assert items[0].get("completed") is None


# ---------------------------------------------------------------------------
# 3. completed="true" (string) is NOT treated as boolean True
# ---------------------------------------------------------------------------


def test_completed_string_true_not_treated_as_bool(tasks_dir: Path):
    """reconcile_completed uses `is True` identity check.

    A string "true" does not satisfy `completed is True`, so the
    completed->status sync branch is NOT triggered. The status stays
    unchanged, and because status != "done" the other branch also does
    not fire -- no modification at all.
    """
    _write(tasks_dir, [
        {"id": "task-001", "title": "X", "status": "open", "completed": "true"},
    ])
    reconcile_completed(cwd=tasks_dir)
    items = _read(tasks_dir)
    # status must remain "open" -- string "true" is not bool True
    assert items[0]["status"] == "open"
    # the string value itself is left untouched
    assert items[0]["completed"] == "true"


# ---------------------------------------------------------------------------
# 4. status=blocked + completed=True -> completed wins, status becomes done
# ---------------------------------------------------------------------------


def test_blocked_with_completed_true_becomes_done(tasks_dir: Path):
    """completed=True overrides blocked status."""
    _write(tasks_dir, [
        {"id": "task-001", "title": "X", "status": "blocked", "completed": True},
    ])
    reconcile_completed(cwd=tasks_dir)
    items = _read(tasks_dir)
    assert items[0]["status"] == "done"


# ---------------------------------------------------------------------------
# 5. status=open + completed=False -> no change
# ---------------------------------------------------------------------------


def test_open_with_completed_false_no_change(tasks_dir: Path):
    """open + completed=False is fully synced; nothing should change."""
    _write(tasks_dir, [
        {"id": "task-001", "title": "X", "status": "open", "completed": False},
    ])
    reconcile_completed(cwd=tasks_dir)
    items = _read(tasks_dir)
    assert items[0]["status"] == "open"
    assert items[0]["completed"] is False


# ---------------------------------------------------------------------------
# 6. empty tasks list -- no error
# ---------------------------------------------------------------------------


def test_empty_tasks_noop(tasks_dir: Path):
    """Empty task list must not raise."""
    _write(tasks_dir, [])
    reconcile_completed(cwd=tasks_dir)  # must not raise
    items = _read(tasks_dir)
    assert items == []


# ---------------------------------------------------------------------------
# 7. already-synced single task -- file not rewritten
# ---------------------------------------------------------------------------


def test_single_task_already_synced_file_not_rewritten(tasks_dir: Path):
    """completed=True + status=done is already consistent; file stays untouched."""
    tasks_yaml = tasks_dir / "tasks.yaml"
    _write(tasks_dir, [
        {"id": "task-001", "title": "X", "status": "done", "completed": True},
    ])
    mtime_before = tasks_yaml.stat().st_mtime_ns

    # Small sleep to ensure mtime would differ if rewritten
    time.sleep(0.01)
    reconcile_completed(cwd=tasks_dir)

    mtime_after = tasks_yaml.stat().st_mtime_ns
    assert mtime_after == mtime_before, "file must not be rewritten when already synced"


# ---------------------------------------------------------------------------
# 8. status=in_progress + completed=True -> status becomes done
# ---------------------------------------------------------------------------


def test_in_progress_with_completed_true_becomes_done(tasks_dir: Path):
    """completed=True overrides in_progress status."""
    _write(tasks_dir, [
        {"id": "task-001", "title": "X", "status": "in_progress", "completed": True},
    ])
    reconcile_completed(cwd=tasks_dir)
    items = _read(tasks_dir)
    assert items[0]["status"] == "done"
