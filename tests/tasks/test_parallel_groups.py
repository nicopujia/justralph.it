"""Deep edge case tests for compute_parallel_groups() and get_next_ready_task()."""

from pathlib import Path

from tasks.main import (
    TaskStatus,
    close_task,
    compute_parallel_groups,
    create_task,
    get_next_ready_task,
    get_task,
    update_task,
)


# ---------------------------------------------------------------------------
# compute_parallel_groups -- edge cases
# ---------------------------------------------------------------------------


def test_empty_tasks_noop(tasks_dir: Path):
    # No tasks.yaml exists at all -- should not raise
    compute_parallel_groups(cwd=tasks_dir)


def test_diamond_dependency(tasks_dir: Path):
    # A (root), B->A, C->A, D->B
    # Expected groups: A=1, B=2, C=2, D=3
    a = create_task("A", cwd=tasks_dir)
    b = create_task("B", parent=a.id, cwd=tasks_dir)
    c = create_task("C", parent=a.id, cwd=tasks_dir)
    d = create_task("D", parent=b.id, cwd=tasks_dir)

    compute_parallel_groups(cwd=tasks_dir)

    assert get_task(a.id, cwd=tasks_dir).parallel_group == 1
    assert get_task(b.id, cwd=tasks_dir).parallel_group == 2
    assert get_task(c.id, cwd=tasks_dir).parallel_group == 2
    assert get_task(d.id, cwd=tasks_dir).parallel_group == 3


def test_orphaned_parent(tasks_dir: Path):
    # Parent ID does not exist in the store -- task should get group 1
    # (by_id lookup fails, _group_of falls back to 1)
    t = create_task("Orphan child", parent="task-999", cwd=tasks_dir)

    compute_parallel_groups(cwd=tasks_dir)

    assert get_task(t.id, cwd=tasks_dir).parallel_group == 1


def test_idempotent(tasks_dir: Path):
    a = create_task("A", cwd=tasks_dir)
    b = create_task("B", parent=a.id, cwd=tasks_dir)
    c = create_task("C", parent=b.id, cwd=tasks_dir)

    compute_parallel_groups(cwd=tasks_dir)
    first_run = {
        a.id: get_task(a.id, cwd=tasks_dir).parallel_group,
        b.id: get_task(b.id, cwd=tasks_dir).parallel_group,
        c.id: get_task(c.id, cwd=tasks_dir).parallel_group,
    }

    compute_parallel_groups(cwd=tasks_dir)
    second_run = {
        a.id: get_task(a.id, cwd=tasks_dir).parallel_group,
        b.id: get_task(b.id, cwd=tasks_dir).parallel_group,
        c.id: get_task(c.id, cwd=tasks_dir).parallel_group,
    }

    assert first_run == second_run


def test_long_chain(tasks_dir: Path):
    # A->B->C->D means D is created last with parent C
    # Creation order: A (no parent), B (parent=A), C (parent=B), D (parent=C)
    # Expected groups: A=1, B=2, C=3, D=4
    a = create_task("A", cwd=tasks_dir)
    b = create_task("B", parent=a.id, cwd=tasks_dir)
    c = create_task("C", parent=b.id, cwd=tasks_dir)
    d = create_task("D", parent=c.id, cwd=tasks_dir)

    compute_parallel_groups(cwd=tasks_dir)

    assert get_task(a.id, cwd=tasks_dir).parallel_group == 1
    assert get_task(b.id, cwd=tasks_dir).parallel_group == 2
    assert get_task(c.id, cwd=tasks_dir).parallel_group == 3
    assert get_task(d.id, cwd=tasks_dir).parallel_group == 4


# ---------------------------------------------------------------------------
# get_next_ready_task -- edge cases
# ---------------------------------------------------------------------------


def test_get_next_ready_task_skips_blocked(tasks_dir: Path):
    # Even if a BLOCKED task's parent is done, it is not OPEN so not eligible
    parent = create_task("Parent", priority=1, cwd=tasks_dir)
    child = create_task("Child", priority=1, parent=parent.id, cwd=tasks_dir)

    close_task(parent.id, cwd=tasks_dir)
    update_task(child.id, status=TaskStatus.BLOCKED, cwd=tasks_dir)

    result = get_next_ready_task(cwd=tasks_dir)
    assert result is None


def test_get_next_ready_task_skips_in_progress(tasks_dir: Path):
    # IN_PROGRESS tasks are not OPEN and must be skipped
    t = create_task("Running", priority=1, cwd=tasks_dir)
    update_task(t.id, status=TaskStatus.IN_PROGRESS, cwd=tasks_dir)

    result = get_next_ready_task(cwd=tasks_dir)
    assert result is None


def test_get_next_ready_task_equal_priority_picks_first(tasks_dir: Path):
    # All have the same priority -- list_tasks preserves YAML order (insertion order)
    # so the first created task should be returned
    t1 = create_task("First", priority=2, cwd=tasks_dir)
    _t2 = create_task("Second", priority=2, cwd=tasks_dir)
    _t3 = create_task("Third", priority=2, cwd=tasks_dir)

    result = get_next_ready_task(cwd=tasks_dir)
    assert result.id == t1.id


def test_get_next_ready_task_parent_not_done(tasks_dir: Path):
    # Child's parent is still OPEN -- child must not be selected
    parent = create_task("Parent", priority=5, cwd=tasks_dir)
    child = create_task("Child", priority=1, parent=parent.id, cwd=tasks_dir)

    # Parent is OPEN (not DONE), so child is ineligible.
    # Parent has no parent constraint, so parent itself is eligible.
    result = get_next_ready_task(cwd=tasks_dir)
    assert result.id == parent.id
    assert result.id != child.id


def test_get_next_ready_task_all_blocked_returns_none(tasks_dir: Path):
    t1 = create_task("X", cwd=tasks_dir)
    t2 = create_task("Y", cwd=tasks_dir)
    update_task(t1.id, status=TaskStatus.BLOCKED, cwd=tasks_dir)
    update_task(t2.id, status=TaskStatus.BLOCKED, cwd=tasks_dir)

    result = get_next_ready_task(cwd=tasks_dir)
    assert result is None
