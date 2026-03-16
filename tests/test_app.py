import json
import os
import sqlite3
import tempfile
import threading

from app import create_app
from app.sse import publish, subscribe, unsubscribe


def test_app_creates():
    app = create_app()
    assert app is not None


def test_index_unauthenticated_returns_200():
    app = create_app({"TESTING": True})
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200


def test_index_unauthenticated_shows_sign_in_button():
    """Unauthenticated user sees 'Sign in with GitHub' on the landing page."""
    app = create_app({"TESTING": True})
    client = app.test_client()
    response = client.get("/")
    assert b"Sign in with GitHub" in response.data


def test_index_authenticated_redirects_to_projects():
    """Authenticated user visiting '/' is redirected to /projects."""
    app = create_app({"TESTING": True})
    app.config["SECRET_KEY"] = "test-secret"
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = {"login": "testuser"}
    response = client.get("/")
    assert response.status_code == 302
    assert "/projects" in response.headers["Location"]


def test_index_unauthenticated_shows_app_description():
    """Landing page shows the app name and description."""
    app = create_app({"TESTING": True})
    client = app.test_client()
    response = client.get("/")
    assert b"justralph.it" in response.data
    assert b"Ralph Wiggum" in response.data


def test_health_returns_ok():
    app = create_app({"TESTING": True})
    client = app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


# --- OPENCODE_URL config tests ---


def test_opencode_url_default():
    """App config has OPENCODE_URL set to the default value."""
    app = create_app({"TESTING": True})
    assert app.config["OPENCODE_URL"] == "http://127.0.0.1:4096"


def test_opencode_url_from_env(monkeypatch):
    """App config uses a custom value when OPENCODE_URL env var is set."""
    monkeypatch.setenv("OPENCODE_URL", "http://custom-host:9999")
    app = create_app()
    assert app.config["OPENCODE_URL"] == "http://custom-host:9999"


def test_opencode_url_default_value():
    """The default for OPENCODE_URL is exactly http://127.0.0.1:4096."""
    env_backup = os.environ.pop("OPENCODE_URL", None)
    try:
        app = create_app({"TESTING": True})
        assert app.config["OPENCODE_URL"] == "http://127.0.0.1:4096"
    finally:
        if env_backup is not None:
            os.environ["OPENCODE_URL"] = env_backup


def test_init_db_creates_projects_table():
    """DB is initialized on app startup with a projects table."""
    db_fd, db_path = tempfile.mkstemp()
    try:
        create_app({"DATABASE": db_path})
        # Table should already exist after create_app
        db = sqlite3.connect(db_path)
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")
        tables = cursor.fetchall()
        db.close()
        assert len(tables) == 1
    finally:
        os.close(db_fd)
        os.unlink(db_path)


# --- Helpers ---


def _make_app():
    """Create app with a temp DB and return (app, db_path, db_fd)."""
    db_fd, db_path = tempfile.mkstemp()
    app = create_app({"DATABASE": db_path, "TESTING": True})
    return app, db_path, db_fd


def _cleanup(db_fd, db_path):
    os.close(db_fd)
    os.unlink(db_path)


def _insert_project(db_path, name, slug, ralph_running=0):
    db = sqlite3.connect(db_path)
    db.execute(
        "INSERT INTO projects (name, slug, ralph_running) VALUES (?, ?, ?)",
        (name, slug, ralph_running),
    )
    db.commit()
    db.close()


# --- Schema tests ---


def test_projects_table_has_slug_column():
    """Projects table must have a slug column."""
    app, db_path, db_fd = _make_app()
    try:
        db = sqlite3.connect(db_path)
        cursor = db.execute("PRAGMA table_info(projects)")
        columns = {row[1] for row in cursor.fetchall()}
        db.close()
        assert "slug" in columns
    finally:
        _cleanup(db_fd, db_path)


def test_projects_table_has_ralph_running_column():
    """Projects table must have a ralph_running column defaulting to 0."""
    app, db_path, db_fd = _make_app()
    try:
        db = sqlite3.connect(db_path)
        db.execute("INSERT INTO projects (name, slug) VALUES ('test', 'test')")
        db.commit()
        row = db.execute("SELECT ralph_running FROM projects WHERE slug='test'").fetchone()
        db.close()
        assert row[0] == 0
    finally:
        _cleanup(db_fd, db_path)


# --- SSE infrastructure tests ---


def test_sse_publish_subscribe():
    """subscribe() returns a queue that receives published events."""
    q = subscribe("myproject")
    try:
        publish("myproject", "show_just_ralph_it_button", {})
        event = q.get(timeout=1)
        assert event["type"] == "show_just_ralph_it_button"
    finally:
        unsubscribe("myproject", q)


def test_sse_unsubscribe():
    """After unsubscribe, queue no longer receives events."""
    q = subscribe("myproject2")
    unsubscribe("myproject2", q)
    publish("myproject2", "test", {})
    assert q.empty()


# --- Internal endpoint tests ---


def test_show_button_returns_404_for_unknown_slug():
    """POST /internal/projects/<slug>/show-button returns 404 for unknown project."""
    app, db_path, db_fd = _make_app()
    try:
        client = app.test_client()
        response = client.post("/internal/projects/nonexistent/show-button")
        assert response.status_code == 404
    finally:
        _cleanup(db_fd, db_path)


def test_show_button_returns_ok_and_pushes_event():
    """POST show-button returns 200 with ok and pushes SSE event when ralph_running=False."""
    app, db_path, db_fd = _make_app()
    try:
        _insert_project(db_path, "Test Project", "test-project", ralph_running=0)
        q = subscribe("test-project")
        try:
            client = app.test_client()
            response = client.post("/internal/projects/test-project/show-button")
            assert response.status_code == 200
            assert response.json["status"] == "ok"
            event = q.get(timeout=1)
            assert event["type"] == "show_just_ralph_it_button"
        finally:
            unsubscribe("test-project", q)
    finally:
        _cleanup(db_fd, db_path)


def test_show_button_returns_noop_when_ralph_running():
    """POST show-button returns 200 with no-op when ralph_running=True."""
    app, db_path, db_fd = _make_app()
    try:
        _insert_project(db_path, "Running Project", "running-proj", ralph_running=1)
        client = app.test_client()
        response = client.post("/internal/projects/running-proj/show-button")
        assert response.status_code == 200
        assert response.json["status"] == "no-op"
        assert response.json["reason"] == "ralph_running"
    finally:
        _cleanup(db_fd, db_path)


def test_sse_events_endpoint_streams():
    """GET /internal/projects/<slug>/events streams SSE events."""
    app, db_path, db_fd = _make_app()
    try:
        _insert_project(db_path, "Stream Project", "stream-proj")

        received = []

        def read_stream():
            client = app.test_client()
            with client.get(
                "/internal/projects/stream-proj/events",
                headers={"Accept": "text/event-stream"},
            ) as response:
                for line in response.iter_encoded():
                    decoded = line.decode("utf-8").strip()
                    if decoded.startswith("data:"):
                        received.append(decoded)
                        break  # one event is enough

        t = threading.Thread(target=read_stream, daemon=True)
        t.start()
        # Give the SSE client time to connect
        import time

        time.sleep(0.3)
        publish("stream-proj", "show_just_ralph_it_button", {"hello": "world"})
        t.join(timeout=3)

        assert len(received) == 1
        payload = json.loads(received[0].removeprefix("data:").strip())
        assert payload["type"] == "show_just_ralph_it_button"
    finally:
        _cleanup(db_fd, db_path)


# --- SECRET_KEY validation tests ---


def test_secret_key_missing_raises(monkeypatch):
    """create_app() raises RuntimeError when SECRET_KEY env var is not set."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    import pytest

    with pytest.raises(RuntimeError):
        create_app({"TESTING": False})


def test_secret_key_dev_raises(monkeypatch):
    """create_app() raises RuntimeError when SECRET_KEY env var is 'dev'."""
    monkeypatch.setenv("SECRET_KEY", "dev")
    import pytest

    with pytest.raises(RuntimeError):
        create_app({"TESTING": False})


def test_secret_key_from_env(monkeypatch):
    """When SECRET_KEY env var is set to a valid value, the app uses it."""
    monkeypatch.setenv("SECRET_KEY", "a-real-secret-key-for-testing")
    app = create_app({"TESTING": True})
    assert app.config["SECRET_KEY"] == "a-real-secret-key-for-testing"


def test_secret_key_from_test_config(monkeypatch):
    """When test_config provides SECRET_KEY, it's used even without env var."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    app = create_app({"TESTING": True, "SECRET_KEY": "test-override"})
    assert app.config["SECRET_KEY"] == "test-override"
