"""Unit tests for server/db.py -- SQLite persistence layer.

Each test gets a fresh isolated DB via monkeypatching server.db._db_path.
"""

import time
from pathlib import Path

import pytest

import server.db as db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect _db_path to a temp file and initialize the schema."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "_db_path", db_file)
    db.init_db()
    yield


# ---------------------------------------------------------------------------
# init_db: table creation
# ---------------------------------------------------------------------------


def test_init_db_creates_users_table():
    conn = db._get_conn()
    result = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone()
    conn.close()
    assert result is not None


def test_init_db_creates_sessions_table():
    conn = db._get_conn()
    result = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
    ).fetchone()
    conn.close()
    assert result is not None


def test_init_db_creates_chat_messages_table():
    conn = db._get_conn()
    result = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_messages'"
    ).fetchone()
    conn.close()
    assert result is not None


def test_init_db_creates_chat_state_table():
    conn = db._get_conn()
    result = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_state'"
    ).fetchone()
    conn.close()
    assert result is not None


def test_init_db_is_idempotent():
    # Calling twice should not raise
    db.init_db()
    db.init_db()


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def _make_session(sid: str = "sess-001") -> None:
    db.save_session(sid, "/tmp/project", "https://github.com/x/y", "ready", time.time())


def test_save_and_load_session():
    _make_session("sess-001")
    result = db.load_session("sess-001")
    assert result is not None
    assert result["id"] == "sess-001"
    assert result["base_dir"] == "/tmp/project"
    assert result["github_url"] == "https://github.com/x/y"
    assert result["status"] == "ready"


def test_load_session_returns_none_for_missing():
    result = db.load_session("no-such-session")
    assert result is None


def test_list_sessions_returns_all():
    _make_session("s1")
    _make_session("s2")
    sessions = db.list_sessions()
    ids = {s["id"] for s in sessions}
    assert "s1" in ids
    assert "s2" in ids


def test_list_sessions_empty_returns_empty_list():
    assert db.list_sessions() == []


def test_save_session_replace_on_duplicate_id():
    _make_session("sess-001")
    db.save_session("sess-001", "/other/dir", "", "running", time.time())
    result = db.load_session("sess-001")
    assert result["base_dir"] == "/other/dir"
    assert result["status"] == "running"


def test_update_session_status():
    _make_session("sess-001")
    db.update_session_status("sess-001", "running")
    result = db.load_session("sess-001")
    assert result["status"] == "running"


def test_update_session_status_to_done():
    _make_session("sess-001")
    db.update_session_status("sess-001", "done")
    result = db.load_session("sess-001")
    assert result["status"] == "done"


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def test_save_and_load_user():
    db.save_user("tok-abc", "gh-token-xyz", "alice", "Alice Smith", "https://avatar.url/a")
    result = db.load_user("tok-abc")
    assert result is not None
    assert result["token"] == "tok-abc"
    assert result["github_token"] == "gh-token-xyz"
    assert result["login"] == "alice"
    assert result["name"] == "Alice Smith"
    assert result["avatar_url"] == "https://avatar.url/a"


def test_load_user_returns_none_for_missing():
    assert db.load_user("nonexistent-token") is None


def test_save_user_replace_on_duplicate_token():
    db.save_user("tok-abc", "gh-old", "alice", None, None)
    db.save_user("tok-abc", "gh-new", "alice-renamed", "Alice", None)
    result = db.load_user("tok-abc")
    assert result["github_token"] == "gh-new"
    assert result["login"] == "alice-renamed"


def test_save_user_nullable_fields():
    db.save_user("tok-xyz", "gh-tok", "bob", None, None)
    result = db.load_user("tok-xyz")
    assert result["name"] is None
    assert result["avatar_url"] is None


def test_save_user_records_created_at():
    before = time.time()
    db.save_user("tok-ts", "gh-tok", "carol", None, None)
    after = time.time()
    result = db.load_user("tok-ts")
    assert before <= result["created_at"] <= after


# ---------------------------------------------------------------------------
# Chat messages
# ---------------------------------------------------------------------------


def _setup_session_and_messages(session_id: str = "sess-001") -> str:
    """Create a session and return its id (messages need a valid session)."""
    db.save_session(session_id, "/tmp", "", "ready", time.time())
    return session_id


def test_save_and_load_chat_messages():
    sid = _setup_session_and_messages()
    db.save_chat_message(sid, "user", "Hello!")
    db.save_chat_message(sid, "assistant", "Hi there!")
    msgs = db.load_chat_messages(sid)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "Hello!"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == "Hi there!"


def test_load_chat_messages_ordered_by_id():
    sid = _setup_session_and_messages()
    db.save_chat_message(sid, "user", "first")
    db.save_chat_message(sid, "assistant", "second")
    db.save_chat_message(sid, "user", "third")
    msgs = db.load_chat_messages(sid)
    contents = [m["content"] for m in msgs]
    assert contents == ["first", "second", "third"]


def test_load_chat_messages_empty_for_unknown_session():
    db.save_session("known", "/tmp", "", "ready", time.time())
    msgs = db.load_chat_messages("unknown-session")
    assert msgs == []


def test_delete_chat_messages():
    sid = _setup_session_and_messages()
    db.save_chat_message(sid, "user", "to be deleted")
    db.delete_chat_messages(sid)
    msgs = db.load_chat_messages(sid)
    assert msgs == []


def test_delete_chat_messages_only_for_given_session():
    sid1 = _setup_session_and_messages("sess-A")
    db.save_session("sess-B", "/tmp", "", "ready", time.time())
    db.save_chat_message(sid1, "user", "keep me")
    db.save_chat_message("sess-B", "user", "delete me")
    db.delete_chat_messages("sess-B")
    assert len(db.load_chat_messages(sid1)) == 1
    assert db.load_chat_messages("sess-B") == []


def test_save_chat_message_records_created_at():
    sid = _setup_session_and_messages()
    before = time.time()
    db.save_chat_message(sid, "user", "timed")
    after = time.time()
    msgs = db.load_chat_messages(sid)
    assert before <= msgs[0]["created_at"] <= after


# ---------------------------------------------------------------------------
# Chat state
# ---------------------------------------------------------------------------

DIMENSIONS = [
    "functional", "technical_stack", "data_model",
    "auth", "deployment", "testing", "edge_cases",
]


def _sample_confidence() -> dict:
    return {d: 75 for d in DIMENSIONS}


def _sample_relevance() -> dict:
    return {d: 0.9 for d in DIMENSIONS}


def test_save_and_load_chat_state():
    db.save_session("sess-cs", "/tmp", "", "ready", time.time())
    conf = _sample_confidence()
    rel = _sample_relevance()
    db.save_chat_state("sess-cs", conf, rel, False, 72.5, None, None)
    result = db.load_chat_state("sess-cs")
    assert result is not None
    assert result["confidence"] == conf
    assert result["relevance"] == rel
    assert result["ready"] is False
    assert result["weighted_readiness"] == 72.5
    assert result["tasks"] is None
    assert result["project"] is None


def test_load_chat_state_returns_none_for_missing_session():
    result = db.load_chat_state("no-such-session")
    assert result is None


def test_save_chat_state_with_tasks_and_project():
    db.save_session("sess-with-tasks", "/tmp", "", "ready", time.time())
    tasks = [{"title": "Task A", "priority": 1}]
    project = {"name": "myapp", "language": "Python"}
    db.save_chat_state("sess-with-tasks", {}, {}, True, 91.0, tasks, project)
    result = db.load_chat_state("sess-with-tasks")
    assert result["tasks"] == tasks
    assert result["project"] == project
    assert result["ready"] is True


def test_save_chat_state_deserializes_confidence_as_dict():
    db.save_session("sess-deser", "/tmp", "", "ready", time.time())
    conf = {"functional": 80, "technical_stack": 60}
    db.save_chat_state("sess-deser", conf, {}, False, 50.0, None, None)
    result = db.load_chat_state("sess-deser")
    assert isinstance(result["confidence"], dict)
    assert result["confidence"]["functional"] == 80


def test_save_chat_state_deserializes_relevance_as_dict():
    db.save_session("sess-rel", "/tmp", "", "ready", time.time())
    rel = {"functional": 1.0, "auth": 0.0}
    db.save_chat_state("sess-rel", {}, rel, False, 0.0, None, None)
    result = db.load_chat_state("sess-rel")
    assert isinstance(result["relevance"], dict)
    assert result["relevance"]["functional"] == 1.0


def test_save_chat_state_replace_on_duplicate_session():
    db.save_session("sess-dup", "/tmp", "", "ready", time.time())
    db.save_chat_state("sess-dup", {"functional": 10}, {}, False, 10.0, None, None)
    db.save_chat_state("sess-dup", {"functional": 90}, {}, True, 90.0, None, None)
    result = db.load_chat_state("sess-dup")
    assert result["confidence"]["functional"] == 90
    assert result["ready"] is True


def test_save_chat_state_ready_boolean_roundtrip_false():
    db.save_session("sess-bool-f", "/tmp", "", "ready", time.time())
    db.save_chat_state("sess-bool-f", {}, {}, False, 0.0, None, None)
    result = db.load_chat_state("sess-bool-f")
    assert result["ready"] is False
    assert isinstance(result["ready"], bool)


def test_save_chat_state_ready_boolean_roundtrip_true():
    db.save_session("sess-bool-t", "/tmp", "", "ready", time.time())
    db.save_chat_state("sess-bool-t", {}, {}, True, 0.0, None, None)
    result = db.load_chat_state("sess-bool-t")
    assert result["ready"] is True
    assert isinstance(result["ready"], bool)


def test_save_chat_state_tasks_list_roundtrip():
    db.save_session("sess-tasks", "/tmp", "", "ready", time.time())
    tasks = [
        {"title": "A", "priority": 1, "parent": None},
        {"title": "B", "priority": 2, "parent": "task-001"},
    ]
    db.save_chat_state("sess-tasks", {}, {}, False, 0.0, tasks, None)
    result = db.load_chat_state("sess-tasks")
    assert result["tasks"] == tasks


def test_save_chat_state_project_dict_roundtrip():
    db.save_session("sess-proj", "/tmp", "", "ready", time.time())
    project = {"name": "cool-app", "language": "TypeScript", "framework": "Next.js"}
    db.save_chat_state("sess-proj", {}, {}, False, 0.0, None, project)
    result = db.load_chat_state("sess-proj")
    assert result["project"] == project


# --- Edge cases (audit additions) ---


def test_update_session_status_nonexistent():
    # UPDATE on a nonexistent id affects 0 rows -- must not raise.
    db.update_session_status("no-such-session", "running")


def test_delete_chat_messages_nonexistent():
    # DELETE on a nonexistent session_id affects 0 rows -- must not raise.
    db.delete_chat_messages("no-such-session")


def test_load_chat_state_empty_json():
    # confidence/relevance stored as "{}" should deserialize to empty dict,
    # not None or raise.
    db.save_session("sess-empty-json", "/tmp", "", "ready", time.time())
    db.save_chat_state("sess-empty-json", {}, {}, False, 0.0, None, None)
    result = db.load_chat_state("sess-empty-json")
    assert isinstance(result["confidence"], dict)
    assert isinstance(result["relevance"], dict)
    assert result["confidence"] == {}
    assert result["relevance"] == {}


def test_save_chat_message_fk_violation():
    # Saving a message for a session that doesn't exist should raise because
    # PRAGMA foreign_keys = ON is set in _get_conn.
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        db.save_chat_message("nonexistent-session", "user", "hello")
