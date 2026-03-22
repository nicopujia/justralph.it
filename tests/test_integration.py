"""Phase 20 integration tests for justralph.it.

Uses FastAPI TestClient (no running server needed).
Each test creates its own session and cleans up after itself.

Isolation strategy:
- DB redirected to a temp file via monkeypatch on server.db._db_path.
- In-memory _sessions dict cleared between tests.
- Session dirs created under tmp_path (via create_session sessions_dir override).
"""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server.db as db
from server.sessions import _sessions, create_session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect DB to temp file, clear in-memory session store, init schema."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "_db_path", db_file)
    db.init_db()
    _sessions.clear()
    yield
    _sessions.clear()


@pytest.fixture()
def client():
    """TestClient with lifespan disabled -- we manage db/session init ourselves."""
    from server.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _create_session_via_api(client: TestClient) -> dict:
    """POST /api/sessions and return the response body."""
    resp = client.post("/api/sessions", json={"github_url": "", "github_token": ""})
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Test 1 (20.1): Session lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_session_create_and_list(client: TestClient):
    """Create session -> list sessions -> get session -> delete."""
    # Create
    data = _create_session_via_api(client)
    sid = data["id"]
    assert sid
    assert data["status"] == "ready"

    # List -- session appears
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert sid in ids

    # Get individual session
    resp = client.get(f"/api/sessions/{sid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == sid

    # Delete
    resp = client.delete(f"/api/sessions/{sid}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    # No longer accessible
    resp = client.get(f"/api/sessions/{sid}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 2 (20.1): Task CRUD inside a session
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_task_crud(client: TestClient, tmp_path: Path):
    """Create task -> list -> get -> update -> delete."""
    session_data = _create_session_via_api(client)
    sid = session_data["id"]

    # Create task
    resp = client.post(
        f"/api/sessions/{sid}/tasks",
        json={"title": "Write tests", "body": "Cover all paths", "priority": 1},
    )
    assert resp.status_code == 201
    task = resp.json()
    tid = task["id"]
    assert task["title"] == "Write tests"
    assert task["status"] == "open"
    assert task["priority"] == 1

    # List tasks -- task appears
    resp = client.get(f"/api/sessions/{sid}/tasks")
    assert resp.status_code == 200
    listed_ids = [t["id"] for t in resp.json()]
    assert tid in listed_ids

    # Get individual task
    resp = client.get(f"/api/sessions/{sid}/tasks/{tid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == tid

    # Update task body and status
    resp = client.patch(
        f"/api/sessions/{sid}/tasks/{tid}",
        json={"body": "Updated body", "status": "done"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "updated"

    # Verify update persisted
    resp = client.get(f"/api/sessions/{sid}/tasks/{tid}")
    updated = resp.json()
    assert updated["body"] == "Updated body"
    assert updated["status"] == "done"

    # Delete task
    resp = client.delete(f"/api/sessions/{sid}/tasks/{tid}")
    assert resp.status_code == 200
    assert resp.json()["task_id"] == tid

    # Task no longer accessible
    resp = client.get(f"/api/sessions/{sid}/tasks/{tid}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 3 (20.3): Chat state persists across DB reload
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_session_state_persists(client: TestClient):
    """Chat state (confidence, messages) persists in DB and survives reload."""
    session_data = _create_session_via_api(client)
    sid = session_data["id"]

    # Persist some chat messages directly via db layer (avoids calling opencode)
    db.save_chat_message(sid, "user", "I want to build a todo app")
    db.save_chat_message(sid, "assistant", '{"message": "Sounds great!", "confidence": {}}')

    # Persist chat state
    conf = {d: 60 for d in [
        "functional", "technical_stack", "data_model",
        "auth", "deployment", "testing", "edge_cases",
    ]}
    db.save_chat_state(sid, conf, {d: 0.8 for d in conf}, False, 55.0, None, None)

    # Verify /chat/history returns persisted data
    resp = client.get(f"/api/sessions/{sid}/chat/history")
    assert resp.status_code == 200
    body = resp.json()
    messages = body["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "I want to build a todo app"

    # State fields are flattened to top level
    assert body["confidence"]["functional"] == 60
    assert body["weighted_readiness"] == 55.0
    assert body["ready"] is False

    # Simulate reload: clear in-memory state, reload from DB
    _sessions.clear()
    from server.sessions import load_sessions_from_db
    load_sessions_from_db()

    # Session accessible again after reload
    resp = client.get(f"/api/sessions/{sid}")
    assert resp.status_code == 200

    # Chat history still intact after reload
    resp = client.get(f"/api/sessions/{sid}/chat/history")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["messages"]) == 2
    assert body["confidence"]["functional"] == 60


# ---------------------------------------------------------------------------
# Test 4 (20.4): Two concurrent sessions don't interfere
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_concurrent_sessions(client: TestClient):
    """Tasks created in session A do not appear in session B."""
    s1 = _create_session_via_api(client)
    s2 = _create_session_via_api(client)
    sid1, sid2 = s1["id"], s2["id"]
    assert sid1 != sid2

    # Create a task in session 1 only
    resp = client.post(
        f"/api/sessions/{sid1}/tasks",
        json={"title": "Task for session 1 only"},
    )
    assert resp.status_code == 201
    tid = resp.json()["id"]

    # Session 1 has the task
    resp = client.get(f"/api/sessions/{sid1}/tasks")
    assert any(t["id"] == tid for t in resp.json())

    # Session 2 has no tasks
    resp = client.get(f"/api/sessions/{sid2}/tasks")
    assert resp.status_code == 200
    assert resp.json() == []

    # Chat state for session 2 is independent (clean baseline)
    resp = client.get(f"/api/sessions/{sid2}/chat/state")
    assert resp.status_code == 200
    state = resp.json()
    # No confidence data bled over from session 1
    assert state.get("ready") is False or state.get("ready") == False  # noqa: E712


# ---------------------------------------------------------------------------
# Test 5 (20.1): Session duplicate -- copies chat history via DB
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_session_duplicate(client: TestClient):
    """Source session chat messages can be read back after copying to a new session.

    There is no /duplicate API endpoint; this test verifies that the DB layer
    supports copying chat messages between sessions (the semantic unit of
    'duplicate chat history').
    """
    # Create source session with some messages
    source = _create_session_via_api(client)
    src_id = source["id"]
    db.save_chat_message(src_id, "user", "Help me build a blog")
    db.save_chat_message(src_id, "assistant", '{"message": "Tell me more.", "confidence": {}}')

    # Create destination session
    dest = _create_session_via_api(client)
    dst_id = dest["id"]

    # Copy messages to the new session (simulates a duplicate operation)
    for msg in db.load_chat_messages(src_id):
        db.save_chat_message(dst_id, msg["role"], msg["content"])

    # Destination session now has the same messages
    resp = client.get(f"/api/sessions/{dst_id}/chat/history")
    assert resp.status_code == 200
    msgs = resp.json()["messages"]
    assert len(msgs) == 2
    assert msgs[0]["content"] == "Help me build a blog"
    assert "Tell me more." in msgs[1]["content"]


# ---------------------------------------------------------------------------
# Test 6: Task delete and reorder
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_task_delete_and_reorder(client: TestClient):
    """Delete a task, reorder remaining tasks."""
    session_data = _create_session_via_api(client)
    sid = session_data["id"]

    # Create three tasks
    t1 = client.post(f"/api/sessions/{sid}/tasks", json={"title": "Alpha", "priority": 1}).json()
    t2 = client.post(f"/api/sessions/{sid}/tasks", json={"title": "Beta", "priority": 2}).json()
    t3 = client.post(f"/api/sessions/{sid}/tasks", json={"title": "Gamma", "priority": 3}).json()

    # Delete the middle task
    resp = client.delete(f"/api/sessions/{sid}/tasks/{t2['id']}")
    assert resp.status_code == 200

    # Verify only two tasks remain
    resp = client.get(f"/api/sessions/{sid}/tasks")
    assert resp.status_code == 200
    remaining = resp.json()
    assert len(remaining) == 2
    remaining_ids = {t["id"] for t in remaining}
    assert t1["id"] in remaining_ids
    assert t3["id"] in remaining_ids
    assert t2["id"] not in remaining_ids

    # Reorder: Gamma first, Alpha second
    resp = client.post(
        f"/api/sessions/{sid}/tasks/reorder",
        json={"task_ids": [t3["id"], t1["id"]]},
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 2

    # Verify priorities updated
    gamma = client.get(f"/api/sessions/{sid}/tasks/{t3['id']}").json()
    alpha = client.get(f"/api/sessions/{sid}/tasks/{t1['id']}").json()
    assert gamma["priority"] == 1
    assert alpha["priority"] == 2


# ---------------------------------------------------------------------------
# Test 7: Error handling -- invalid session / missing task
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_error_responses(client: TestClient):
    """Invalid session IDs, missing tasks return proper error codes."""
    phantom_id = "nonexistent-session-id"

    # Unknown session -> 404
    resp = client.get(f"/api/sessions/{phantom_id}")
    assert resp.status_code == 404

    resp = client.get(f"/api/sessions/{phantom_id}/tasks")
    assert resp.status_code == 404

    resp = client.post(
        f"/api/sessions/{phantom_id}/tasks",
        json={"title": "Ghost task"},
    )
    assert resp.status_code == 404

    # Valid session, unknown task -> 404
    session_data = _create_session_via_api(client)
    sid = session_data["id"]

    resp = client.get(f"/api/sessions/{sid}/tasks/task-999")
    assert resp.status_code == 404

    resp = client.patch(
        f"/api/sessions/{sid}/tasks/task-999",
        json={"status": "done"},
    )
    assert resp.status_code == 404

    resp = client.delete(f"/api/sessions/{sid}/tasks/task-999")
    assert resp.status_code == 404

    # Deleting a session twice -> second attempt 404
    client.delete(f"/api/sessions/{sid}")
    resp = client.delete(f"/api/sessions/{sid}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 8: Rename session (PATCH /api/sessions/{id})
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_session_rename(client: TestClient):
    """Rename session persists the name field."""
    session_data = _create_session_via_api(client)
    sid = session_data["id"]

    resp = client.patch(f"/api/sessions/{sid}", json={"name": "My Cool Project"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "My Cool Project"

    # Name persists on GET
    resp = client.get(f"/api/sessions/{sid}")
    assert resp.json()["name"] == "My Cool Project"


# ---------------------------------------------------------------------------
# Test 9: Task filter by status
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_task_list_filter_by_status(client: TestClient):
    """GET /tasks?status=done returns only done tasks."""
    session_data = _create_session_via_api(client)
    sid = session_data["id"]

    t1 = client.post(
        f"/api/sessions/{sid}/tasks", json={"title": "Open task"}
    ).json()
    t2 = client.post(
        f"/api/sessions/{sid}/tasks", json={"title": "Done task"}
    ).json()

    # Mark t2 as done
    client.patch(f"/api/sessions/{sid}/tasks/{t2['id']}", json={"status": "done"})

    # Filter by done
    resp = client.get(f"/api/sessions/{sid}/tasks?status=done")
    assert resp.status_code == 200
    done_tasks = resp.json()
    assert all(t["status"] == "done" for t in done_tasks)
    done_ids = [t["id"] for t in done_tasks]
    assert t2["id"] in done_ids
    assert t1["id"] not in done_ids


# ---------------------------------------------------------------------------
# Test 10: Task with parent cleared after parent deleted
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_delete_parent_task_clears_child_parent_ref(client: TestClient):
    """Deleting a parent task clears the parent field on child tasks."""
    session_data = _create_session_via_api(client)
    sid = session_data["id"]

    parent = client.post(
        f"/api/sessions/{sid}/tasks", json={"title": "Parent task"}
    ).json()
    child = client.post(
        f"/api/sessions/{sid}/tasks",
        json={"title": "Child task", "parent": parent["id"]},
    ).json()

    # Delete parent
    resp = client.delete(f"/api/sessions/{sid}/tasks/{parent['id']}")
    assert resp.status_code == 200

    # Child still exists but parent ref cleared
    child_data = client.get(f"/api/sessions/{sid}/tasks/{child['id']}").json()
    assert child_data["id"] == child["id"]
    # parent field should be empty string or absent after parent deletion
    assert child_data.get("parent", "") == ""


# ---------------------------------------------------------------------------
# Test 11: Chat state endpoint returns clean baseline
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_chat_state_baseline(client: TestClient):
    """New session returns a clean, zeroed chat state."""
    session_data = _create_session_via_api(client)
    sid = session_data["id"]

    resp = client.get(f"/api/sessions/{sid}/chat/state")
    assert resp.status_code == 200
    state = resp.json()
    assert state["ready"] is False
    assert state["weighted_readiness"] == 0


# ---------------------------------------------------------------------------
# Test 12: Chat clear resets in-memory state
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_chat_clear_resets_state(client: TestClient):
    """POST /chat/clear removes all chat messages and resets confidence."""
    session_data = _create_session_via_api(client)
    sid = session_data["id"]

    # Seed some messages and state directly in DB
    db.save_chat_message(sid, "user", "hello")
    conf = {d: 80 for d in [
        "functional", "technical_stack", "data_model",
        "auth", "deployment", "testing", "edge_cases",
    ]}
    db.save_chat_state(sid, conf, {}, False, 70.0, None, None)

    # Clear
    resp = client.post(f"/api/sessions/{sid}/chat/clear")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cleared"

    # Messages are gone from DB
    msgs = db.load_chat_messages(sid)
    assert msgs == []

    # In-memory state is reset
    resp = client.get(f"/api/sessions/{sid}/chat/state")
    state = resp.json()
    assert state["ready"] is False
    assert state["weighted_readiness"] == 0
