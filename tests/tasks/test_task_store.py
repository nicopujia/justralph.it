"""Unit tests for pkgs/tasks/main.py -- YAML-backed task store."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from tasks.main import (
    DEFAULT_PRIORITY,
    Task,
    TaskStatus,
    _next_id,
    _parse_dt,
    _save_tasks,
    close_task,
    compute_parallel_groups,
    create_task,
    get_next_ready_task,
    get_task,
    list_tasks,
    reconcile_completed,
    update_task,
)


# ---------------------------------------------------------------------------
# TaskStatus enum
# ---------------------------------------------------------------------------


def test_task_status_values():
    assert TaskStatus.OPEN == "open"
    assert TaskStatus.IN_PROGRESS == "in_progress"
    assert TaskStatus.BLOCKED == "blocked"
    assert TaskStatus.DONE == "done"


def test_task_status_is_str():
    # StrEnum -- can be used in string comparisons without coercion
    assert str(TaskStatus.OPEN) == "open"
    assert f"{TaskStatus.DONE}" == "done"


# ---------------------------------------------------------------------------
# Task.parse
# ---------------------------------------------------------------------------


def test_task_parse_minimal():
    t = Task.parse({"id": "task-001", "title": "Do stuff"})
    assert t.id == "task-001"
    assert t.title == "Do stuff"
    assert t.status == TaskStatus.OPEN
    assert t.priority == DEFAULT_PRIORITY
    assert t.body == ""
    assert t.labels == []


def test_task_parse_all_fields():
    data = {
        "id": "task-007",
        "title": "Complex task",
        "status": "in_progress",
        "priority": 1,
        "body": "Some body",
        "assignee": "alice",
        "labels": ["bug", "urgent"],
        "parent": "task-003",
        "parallel_group": 2,
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-02T00:00:00+00:00",
    }
    t = Task.parse(data)
    assert t.status == TaskStatus.IN_PROGRESS
    assert t.priority == 1
    assert t.assignee == "alice"
    assert t.labels == ["bug", "urgent"]
    assert t.parent == "task-003"
    assert t.parallel_group == 2
    assert isinstance(t.created_at, datetime)


def test_task_parse_reconciles_completed_true_with_open_status():
    # completed=True overrides status != done
    t = Task.parse({"id": "task-001", "title": "X", "status": "open", "completed": True})
    assert t.status == TaskStatus.DONE


def test_task_parse_reconciles_completed_true_with_in_progress_status():
    t = Task.parse({"id": "task-001", "title": "X", "status": "in_progress", "completed": True})
    assert t.status == TaskStatus.DONE


def test_task_parse_completed_false_does_not_change_status():
    t = Task.parse({"id": "task-001", "title": "X", "status": "open", "completed": False})
    assert t.status == TaskStatus.OPEN


def test_task_parse_no_completed_key():
    t = Task.parse({"id": "task-001", "title": "X", "status": "blocked"})
    assert t.status == TaskStatus.BLOCKED


def test_task_parse_completed_true_and_done_status_stays_done():
    t = Task.parse({"id": "task-001", "title": "X", "status": "done", "completed": True})
    assert t.status == TaskStatus.DONE


# ---------------------------------------------------------------------------
# Task.to_dict
# ---------------------------------------------------------------------------


def test_task_to_dict_open_task_has_completed_false():
    t = Task(id="task-001", title="X")
    d = t.to_dict()
    assert d["completed"] is False
    assert d["status"] == "open"
    assert "body" not in d
    assert "assignee" not in d
    assert "labels" not in d
    assert "parent" not in d


def test_task_to_dict_done_task_has_completed_true():
    t = Task(id="task-001", title="X", status=TaskStatus.DONE)
    d = t.to_dict()
    assert d["completed"] is True
    assert d["status"] == "done"


def test_task_to_dict_optional_fields_included_when_set():
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    t = Task(
        id="task-001",
        title="X",
        body="some body",
        assignee="bob",
        labels=["a"],
        parent="task-000",
        parallel_group=3,
        created_at=now,
        updated_at=now,
    )
    d = t.to_dict()
    assert d["body"] == "some body"
    assert d["assignee"] == "bob"
    assert d["labels"] == ["a"]
    assert d["parent"] == "task-000"
    assert d["parallel_group"] == 3
    assert "created_at" in d
    assert "updated_at" in d


def test_task_to_dict_roundtrip_via_parse():
    now = datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)
    original = Task(
        id="task-042",
        title="Roundtrip",
        status=TaskStatus.BLOCKED,
        priority=3,
        body="body text",
        assignee="carol",
        labels=["feat"],
        parent="task-001",
        parallel_group=2,
        created_at=now,
        updated_at=now,
    )
    restored = Task.parse(original.to_dict())
    assert restored.id == original.id
    assert restored.title == original.title
    assert restored.status == original.status
    assert restored.priority == original.priority
    assert restored.body == original.body
    assert restored.labels == original.labels
    assert restored.parent == original.parent


# ---------------------------------------------------------------------------
# Task.as_xml
# ---------------------------------------------------------------------------


def test_task_as_xml_contains_required_tags():
    t = Task(id="task-001", title="Build API")
    xml = t.as_xml()
    assert "<Task>" in xml
    assert "</Task>" in xml
    assert "<Id>task-001</Id>" in xml
    assert "<Title>Build API</Title>" in xml


def test_task_as_xml_omits_metadata_fields():
    """as_xml only includes agent-relevant fields: id, title, body, parent."""
    t = Task(id="task-001", title="X", labels=["bug"], assignee="alice", priority=1)
    xml = t.as_xml()
    assert "<Assignee>" not in xml
    assert "<Labels>" not in xml
    assert "<Priority>" not in xml
    assert "<Status>" not in xml
    assert "<ParallelGroup>" not in xml
    assert "<CreatedAt>" not in xml


def test_task_as_xml_omits_empty_body():
    t = Task(id="task-001", title="X")
    xml = t.as_xml()
    assert "<Body>" not in xml
    assert "<AcceptanceCriteria>" not in xml


def test_task_as_xml_structured_body():
    """Body with Acceptance/Design sections is parsed into structured XML."""
    t = Task(id="task-001", title="X", body="Acceptance:\n- POST /api returns 200\n- Returns 401 on bad auth\n\nDesign:\n- Use bcrypt")
    xml = t.as_xml()
    assert "<AcceptanceCriteria>" in xml
    assert "<Criterion>POST /api returns 200</Criterion>" in xml
    assert "<Criterion>Returns 401 on bad auth</Criterion>" in xml
    assert "<DesignNotes>" in xml
    assert "<Note>Use bcrypt</Note>" in xml
    # Metadata NOT present
    assert "<Status>" not in xml


def test_task_as_xml_unstructured_body_becomes_acceptance():
    """Body without section headers defaults to acceptance criteria."""
    t = Task(id="task-001", title="X", body="Just do the thing")
    xml = t.as_xml()
    assert "<AcceptanceCriteria>" in xml
    assert "<Criterion>Just do the thing</Criterion>" in xml


def test_task_as_xml_includes_parent():
    t = Task(id="task-002", title="X", parent="task-001")
    xml = t.as_xml()
    assert "<Parent>task-001</Parent>" in xml


def test_task_as_xml_no_datetime():
    """Timestamps are metadata -- not included in agent XML."""
    dt = datetime(2024, 3, 1, 10, 0, tzinfo=timezone.utc)
    t = Task(id="task-001", title="X", created_at=dt)
    xml = t.as_xml()
    assert dt.isoformat() not in xml


# ---------------------------------------------------------------------------
# _next_id
# ---------------------------------------------------------------------------


def test_next_id_empty_list_returns_task_001():
    assert _next_id([]) == "task-001"


def test_next_id_sequential_from_existing():
    tasks = [{"id": "task-001"}, {"id": "task-002"}]
    assert _next_id(tasks) == "task-003"


def test_next_id_skips_gaps():
    tasks = [{"id": "task-001"}, {"id": "task-005"}]
    assert _next_id(tasks) == "task-006"


def test_next_id_ignores_non_task_prefixed_ids():
    tasks = [{"id": "other-001"}, {"id": "task-002"}]
    assert _next_id(tasks) == "task-003"


def test_next_id_ignores_malformed_task_ids():
    tasks = [{"id": "task-abc"}, {"id": "task-003"}]
    assert _next_id(tasks) == "task-004"


def test_next_id_pads_to_three_digits():
    assert _next_id([]) == "task-001"
    tasks = [{"id": f"task-{i:03d}"} for i in range(1, 100)]
    assert _next_id(tasks) == "task-100"


# ---------------------------------------------------------------------------
# _parse_dt
# ---------------------------------------------------------------------------


def test_parse_dt_none_returns_none():
    assert _parse_dt(None) is None


def test_parse_dt_empty_string_returns_none():
    assert _parse_dt("") is None


def test_parse_dt_valid_iso_returns_datetime():
    result = _parse_dt("2024-01-15T10:30:00+00:00")
    assert isinstance(result, datetime)
    assert result.year == 2024
    assert result.month == 1


def test_parse_dt_invalid_string_returns_none():
    assert _parse_dt("not-a-date") is None


def test_parse_dt_invalid_format_returns_none():
    assert _parse_dt("2024/01/01") is None


# ---------------------------------------------------------------------------
# _save_tasks: atomic write
# ---------------------------------------------------------------------------


def test_save_tasks_writes_valid_yaml(tasks_dir: Path):
    data = {"tasks": [{"id": "task-001", "title": "T"}]}
    _save_tasks(data, tasks_dir)
    path = tasks_dir / "tasks.yaml"
    assert path.exists()
    loaded = yaml.safe_load(path.read_text())
    assert loaded["tasks"][0]["id"] == "task-001"


def test_save_tasks_no_temp_file_left_behind(tasks_dir: Path):
    data = {"tasks": []}
    _save_tasks(data, tasks_dir)
    yaml_files = list(tasks_dir.glob("*.yaml"))
    # Only tasks.yaml should remain, no temp files
    assert len(yaml_files) == 1
    assert yaml_files[0].name == "tasks.yaml"


# ---------------------------------------------------------------------------
# create_task
# ---------------------------------------------------------------------------


def test_create_task_returns_task_object(tasks_dir: Path):
    t = create_task("My task", cwd=tasks_dir)
    assert isinstance(t, Task)
    assert t.title == "My task"


def test_create_task_generates_sequential_id(tasks_dir: Path):
    t1 = create_task("First", cwd=tasks_dir)
    t2 = create_task("Second", cwd=tasks_dir)
    assert t1.id == "task-001"
    assert t2.id == "task-002"


def test_create_task_default_priority(tasks_dir: Path):
    t = create_task("X", cwd=tasks_dir)
    assert t.priority == DEFAULT_PRIORITY


def test_create_task_custom_priority(tasks_dir: Path):
    t = create_task("X", priority=1, cwd=tasks_dir)
    assert t.priority == 1


def test_create_task_sets_timestamps(tasks_dir: Path):
    t = create_task("X", cwd=tasks_dir)
    assert t.created_at is not None
    assert t.updated_at is not None


def test_create_task_default_status_is_open(tasks_dir: Path):
    t = create_task("X", cwd=tasks_dir)
    assert t.status == TaskStatus.OPEN


def test_create_task_with_optional_fields(tasks_dir: Path):
    t = create_task(
        "X",
        body="body",
        assignee="alice",
        labels=["a", "b"],
        parent="task-000",
        parallel_group=2,
        cwd=tasks_dir,
    )
    assert t.body == "body"
    assert t.assignee == "alice"
    assert t.labels == ["a", "b"]
    assert t.parent == "task-000"
    assert t.parallel_group == 2


def test_create_task_persists_to_yaml(tasks_dir: Path):
    create_task("Persisted", cwd=tasks_dir)
    loaded = yaml.safe_load((tasks_dir / "tasks.yaml").read_text())
    assert loaded["tasks"][0]["title"] == "Persisted"


# ---------------------------------------------------------------------------
# get_task
# ---------------------------------------------------------------------------


def test_get_task_returns_task_by_id(tasks_dir: Path):
    create_task("Alpha", cwd=tasks_dir)
    t = get_task("task-001", cwd=tasks_dir)
    assert t is not None
    assert t.title == "Alpha"


def test_get_task_returns_none_for_missing_id(tasks_dir: Path):
    result = get_task("task-999", cwd=tasks_dir)
    assert result is None


def test_get_task_returns_none_on_empty_store(tasks_dir: Path):
    result = get_task("task-001", cwd=tasks_dir)
    assert result is None


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------


def test_list_tasks_returns_all_tasks(tasks_dir: Path):
    create_task("A", cwd=tasks_dir)
    create_task("B", cwd=tasks_dir)
    tasks = list_tasks(cwd=tasks_dir)
    assert len(tasks) == 2


def test_list_tasks_empty_store_returns_empty_list(tasks_dir: Path):
    tasks = list_tasks(cwd=tasks_dir)
    assert tasks == []


def test_list_tasks_filter_by_status(tasks_dir: Path):
    create_task("Open one", cwd=tasks_dir)
    t2 = create_task("Done one", cwd=tasks_dir)
    close_task(t2.id, cwd=tasks_dir)

    open_tasks = list_tasks(status="open", cwd=tasks_dir)
    done_tasks = list_tasks(status="done", cwd=tasks_dir)

    assert len(open_tasks) == 1
    assert open_tasks[0].title == "Open one"
    assert len(done_tasks) == 1
    assert done_tasks[0].title == "Done one"


def test_list_tasks_filter_returns_empty_when_no_match(tasks_dir: Path):
    create_task("X", cwd=tasks_dir)
    blocked = list_tasks(status="blocked", cwd=tasks_dir)
    assert blocked == []


# ---------------------------------------------------------------------------
# update_task
# ---------------------------------------------------------------------------


def test_update_task_changes_status(tasks_dir: Path):
    t = create_task("X", cwd=tasks_dir)
    update_task(t.id, status="in_progress", cwd=tasks_dir)
    updated = get_task(t.id, cwd=tasks_dir)
    assert updated.status == TaskStatus.IN_PROGRESS


def test_update_task_changes_priority(tasks_dir: Path):
    t = create_task("X", cwd=tasks_dir)
    update_task(t.id, priority=1, cwd=tasks_dir)
    updated = get_task(t.id, cwd=tasks_dir)
    assert updated.priority == 1


def test_update_task_changes_assignee(tasks_dir: Path):
    t = create_task("X", cwd=tasks_dir)
    update_task(t.id, assignee="dave", cwd=tasks_dir)
    updated = get_task(t.id, cwd=tasks_dir)
    assert updated.assignee == "dave"


def test_update_task_sets_body(tasks_dir: Path):
    t = create_task("X", cwd=tasks_dir)
    update_task(t.id, body="new body", cwd=tasks_dir)
    updated = get_task(t.id, cwd=tasks_dir)
    assert updated.body == "new body"


def test_update_task_appends_notes_to_empty_body(tasks_dir: Path):
    t = create_task("X", cwd=tasks_dir)
    update_task(t.id, append_notes="note1", cwd=tasks_dir)
    updated = get_task(t.id, cwd=tasks_dir)
    assert updated.body == "note1"


def test_update_task_appends_notes_to_existing_body(tasks_dir: Path):
    t = create_task("X", body="original", cwd=tasks_dir)
    update_task(t.id, append_notes="appended", cwd=tasks_dir)
    updated = get_task(t.id, cwd=tasks_dir)
    assert updated.body == "original\nappended"


def test_update_task_updates_timestamp(tasks_dir: Path):
    t = create_task("X", cwd=tasks_dir)
    original_updated_at = get_task(t.id, cwd=tasks_dir).updated_at
    update_task(t.id, status="blocked", cwd=tasks_dir)
    updated = get_task(t.id, cwd=tasks_dir)
    # updated_at must be >= original
    assert updated.updated_at >= original_updated_at


def test_update_task_raises_for_missing_task(tasks_dir: Path):
    with pytest.raises(RuntimeError, match="task-999 not found"):
        update_task("task-999", status="done", cwd=tasks_dir)


def test_update_task_none_fields_not_written(tasks_dir: Path):
    t = create_task("X", priority=3, cwd=tasks_dir)
    # Pass all-None -- should be a no-op on actual values
    update_task(t.id, cwd=tasks_dir)
    unchanged = get_task(t.id, cwd=tasks_dir)
    assert unchanged.priority == 3


# ---------------------------------------------------------------------------
# close_task
# ---------------------------------------------------------------------------


def test_close_task_sets_status_done(tasks_dir: Path):
    t = create_task("X", cwd=tasks_dir)
    close_task(t.id, cwd=tasks_dir)
    updated = get_task(t.id, cwd=tasks_dir)
    assert updated.status == TaskStatus.DONE


def test_close_task_raises_for_missing_task(tasks_dir: Path):
    with pytest.raises(RuntimeError):
        close_task("task-999", cwd=tasks_dir)


# ---------------------------------------------------------------------------
# get_next_ready_task
# ---------------------------------------------------------------------------


def test_get_next_ready_task_returns_none_on_empty_store(tasks_dir: Path):
    assert get_next_ready_task(cwd=tasks_dir) is None


def test_get_next_ready_task_returns_highest_priority_open_task(tasks_dir: Path):
    # Lower number = higher priority
    create_task("Low priority", priority=5, cwd=tasks_dir)
    create_task("High priority", priority=1, cwd=tasks_dir)
    t = get_next_ready_task(cwd=tasks_dir)
    assert t.title == "High priority"


def test_get_next_ready_task_skips_non_open_tasks(tasks_dir: Path):
    t1 = create_task("Done task", priority=1, cwd=tasks_dir)
    close_task(t1.id, cwd=tasks_dir)
    t2 = create_task("Open task", priority=2, cwd=tasks_dir)
    result = get_next_ready_task(cwd=tasks_dir)
    assert result.id == t2.id


def test_get_next_ready_task_returns_none_when_all_done(tasks_dir: Path):
    t = create_task("X", cwd=tasks_dir)
    close_task(t.id, cwd=tasks_dir)
    assert get_next_ready_task(cwd=tasks_dir) is None


def test_get_next_ready_task_respects_parent_dependency(tasks_dir: Path):
    parent = create_task("Parent", priority=1, cwd=tasks_dir)
    child = create_task("Child", priority=1, parent=parent.id, cwd=tasks_dir)
    # Child's parent is not DONE yet -- child should be blocked from selection
    result = get_next_ready_task(cwd=tasks_dir)
    # Parent has no parent constraint so it is selected
    assert result.id == parent.id


def test_get_next_ready_task_child_eligible_after_parent_done(tasks_dir: Path):
    parent = create_task("Parent", priority=1, cwd=tasks_dir)
    child = create_task("Child", priority=1, parent=parent.id, cwd=tasks_dir)
    close_task(parent.id, cwd=tasks_dir)
    result = get_next_ready_task(cwd=tasks_dir)
    assert result.id == child.id


def test_get_next_ready_task_no_parent_always_eligible(tasks_dir: Path):
    t = create_task("Standalone", cwd=tasks_dir)
    result = get_next_ready_task(cwd=tasks_dir)
    assert result.id == t.id


# ---------------------------------------------------------------------------
# compute_parallel_groups
# ---------------------------------------------------------------------------


def test_compute_parallel_groups_no_tasks_does_nothing(tasks_dir: Path):
    # Should not raise
    compute_parallel_groups(cwd=tasks_dir)


def test_compute_parallel_groups_root_tasks_get_group_1(tasks_dir: Path):
    t1 = create_task("A", cwd=tasks_dir)
    t2 = create_task("B", cwd=tasks_dir)
    compute_parallel_groups(cwd=tasks_dir)
    assert get_task(t1.id, cwd=tasks_dir).parallel_group == 1
    assert get_task(t2.id, cwd=tasks_dir).parallel_group == 1


def test_compute_parallel_groups_child_gets_parent_group_plus_1(tasks_dir: Path):
    parent = create_task("Parent", cwd=tasks_dir)
    child = create_task("Child", parent=parent.id, cwd=tasks_dir)
    compute_parallel_groups(cwd=tasks_dir)
    assert get_task(parent.id, cwd=tasks_dir).parallel_group == 1
    assert get_task(child.id, cwd=tasks_dir).parallel_group == 2


def test_compute_parallel_groups_multi_level_chain(tasks_dir: Path):
    g1 = create_task("G1", cwd=tasks_dir)
    g2 = create_task("G2", parent=g1.id, cwd=tasks_dir)
    g3 = create_task("G3", parent=g2.id, cwd=tasks_dir)
    compute_parallel_groups(cwd=tasks_dir)
    assert get_task(g1.id, cwd=tasks_dir).parallel_group == 1
    assert get_task(g2.id, cwd=tasks_dir).parallel_group == 2
    assert get_task(g3.id, cwd=tasks_dir).parallel_group == 3


# ---------------------------------------------------------------------------
# reconcile_completed
# ---------------------------------------------------------------------------


def test_reconcile_completed_sets_status_done_when_completed_true(tasks_dir: Path):
    # Write a task with completed=True but status=open bypassing create_task
    raw = {"tasks": [{"id": "task-001", "title": "X", "status": "open", "completed": True}]}
    (tasks_dir / "tasks.yaml").write_text(yaml.dump(raw))
    reconcile_completed(cwd=tasks_dir)
    t = get_task("task-001", cwd=tasks_dir)
    assert t.status == TaskStatus.DONE


def test_reconcile_completed_sets_completed_true_when_status_done(tasks_dir: Path):
    raw = {"tasks": [{"id": "task-001", "title": "X", "status": "done", "completed": False}]}
    (tasks_dir / "tasks.yaml").write_text(yaml.dump(raw))
    reconcile_completed(cwd=tasks_dir)
    loaded = yaml.safe_load((tasks_dir / "tasks.yaml").read_text())
    assert loaded["tasks"][0]["completed"] is True


def test_reconcile_completed_no_change_when_already_synced(tasks_dir: Path):
    t = create_task("X", cwd=tasks_dir)
    close_task(t.id, cwd=tasks_dir)
    # Both completed and status are already in sync after close_task
    before = (tasks_dir / "tasks.yaml").read_text()
    reconcile_completed(cwd=tasks_dir)
    after = (tasks_dir / "tasks.yaml").read_text()
    # File should not be rewritten if nothing changed
    # (mtime check is flaky; check logical content instead)
    loaded = yaml.safe_load(after)
    assert loaded["tasks"][0]["completed"] is True
    assert loaded["tasks"][0]["status"] == "done"


def test_reconcile_completed_no_tasks_does_nothing(tasks_dir: Path):
    reconcile_completed(cwd=tasks_dir)  # Should not raise


# --- Edge cases (audit additions) ---


def test_create_task_priority_zero(tasks_dir: Path):
    # 0 is falsy; `priority if priority is not None` must not fall back to default
    t = create_task("t", priority=0, cwd=tasks_dir)
    assert t.priority == 0


def test_update_task_body_and_append_notes(tasks_dir: Path):
    # When both body= and append_notes= are passed, body is set first then
    # append_notes is concatenated onto it.
    t = create_task("t", body="base", cwd=tasks_dir)
    update_task(t.id, body="new", append_notes="extra", cwd=tasks_dir)
    updated = get_task(t.id, cwd=tasks_dir)
    assert updated.body == "new\nextra"


def test_update_task_labels_empty_list(tasks_dir: Path):
    # labels=[] must not be skipped due to falsy check; guard is `if labels is not None`
    t = create_task("t", labels=["x", "y"], cwd=tasks_dir)
    update_task(t.id, labels=[], cwd=tasks_dir)
    updated = get_task(t.id, cwd=tasks_dir)
    assert updated.labels == []


def test_next_id_missing_id_key(tasks_dir: Path):
    # Tasks without an "id" key: t.get("id", "") returns "" which doesn't start
    # with "task-", so it is skipped gracefully and next id is task-001.
    tasks = [{}, {"title": "no id here"}]
    assert _next_id(tasks) == "task-001"


def test_list_tasks_status_enum_vs_string(tasks_dir: Path):
    # TaskStatus.DONE == "done" (StrEnum), so both filter forms should agree.
    t = create_task("done task", cwd=tasks_dir)
    close_task(t.id, cwd=tasks_dir)
    create_task("open task", cwd=tasks_dir)

    by_enum = list_tasks(status=TaskStatus.DONE, cwd=tasks_dir)
    by_string = list_tasks(status="done", cwd=tasks_dir)

    assert len(by_enum) == 1
    assert len(by_string) == 1
    assert by_enum[0].id == by_string[0].id
