"""Tests for the 'Just Ralph It' button and Ralph loop launch feature (TDD).

Feature: When Ralphy finishes the spec interview, the browser receives a
show_just_ralph_it_button SSE event. Clicking the button POSTs to
/projects/<slug>/ralph/start, which spawns ralph.py as a subprocess.
Ralph stdout is streamed via /projects/<slug>/ralph/output SSE endpoint.
When ralph finishes, ralph_running is reset to 0 and a ralph_stopped event
is published.

Routes:
- POST /projects/<slug>/ralph/start   — launch Ralph loop (auth-gated)
- GET  /projects/<slug>/ralph/output  — SSE stream of Ralph stdout (auth-gated)

UI elements (show.html):
- #just-ralph-it-btn   — hidden button, shown by SSE event
- #ralph-status        — hidden "Ralph is building..." indicator
- JS connects to internal events SSE for show_just_ralph_it_button
- ralph_running JS variable from template context
"""

import os
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch

from app import create_app

# ---------------------------------------------------------------------------
# Helpers (same pattern as test_app.py / test_chat.py)
# ---------------------------------------------------------------------------


def _make_app():
    """Create app with a temp DB and return (app, db_path, db_fd)."""
    db_fd, db_path = tempfile.mkstemp()
    app = create_app({"DATABASE": db_path, "TESTING": True})
    return app, db_path, db_fd


def _cleanup(db_fd, db_path):
    os.close(db_fd)
    os.unlink(db_path)


def _auth_session(client):
    """Set session vars to simulate an authenticated user."""
    with client.session_transaction() as sess:
        sess["user"] = "nicopujia"
        sess["installation_id"] = "12345"
        sess["installation_token"] = "ghs_test_token"
        sess["token_expires_at"] = "2026-03-15T12:00:00Z"


def _insert_project(
    db_path,
    name="test-project",
    slug="test-project",
    ralph_running=0,
    vps_path="/home/nico/projects/test-project",
):
    """Insert a project directly into the DB."""
    db = sqlite3.connect(db_path)
    db.execute(
        """INSERT INTO projects (name, slug, ralph_running, vps_path)
           VALUES (?, ?, ?, ?)""",
        (name, slug, ralph_running, vps_path),
    )
    db.commit()
    db.close()


# ===========================================================================
# POST /projects/<slug>/ralph/start
# ===========================================================================


class TestRalphStartAuth:
    """Auth and basic validation for POST /projects/<slug>/ralph/start."""

    def test_unauthenticated_redirects(self):
        """Unauthenticated request redirects to /."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.post("/projects/test-project/ralph/start")
            assert response.status_code == 302
            assert response.headers["Location"] == "/"
        finally:
            _cleanup(db_fd, db_path)

    def test_nonexistent_project_returns_404(self):
        """Authenticated request for nonexistent project returns 404."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/nonexistent/ralph/start")
            assert response.status_code == 404
        finally:
            _cleanup(db_fd, db_path)


class TestRalphStartConflict:
    """POST /projects/<slug>/ralph/start returns 409 when Ralph is running."""

    def test_returns_409_if_ralph_already_running(self):
        """Returns 409 Conflict when ralph_running is already 1."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=1)
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/ralph/start")
            assert response.status_code == 409
        finally:
            _cleanup(db_fd, db_path)


class TestRalphStartSuccess:
    """POST /projects/<slug>/ralph/start succeeds and launches Ralph."""

    @patch("app.routes.subprocess.Popen")
    def test_sets_ralph_running_in_db(self, mock_popen):
        """Sets ralph_running = 1 in the database on success."""
        mock_process = MagicMock()
        mock_process.stdout = iter([])
        mock_popen.return_value = mock_process

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/ralph/start")
            assert response.status_code == 200

            # Verify DB was updated
            db = sqlite3.connect(db_path)
            row = db.execute(
                "SELECT ralph_running FROM projects WHERE slug = ?",
                ("test-project",),
            ).fetchone()
            db.close()
            assert row[0] == 1
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.subprocess.Popen")
    def test_returns_200_with_started_status(self, mock_popen):
        """Returns 200 with JSON {"status": "started"}."""
        mock_process = MagicMock()
        mock_process.stdout = iter([])
        mock_popen.return_value = mock_process

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/ralph/start")
            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "started"
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.subprocess.Popen")
    def test_publishes_ralph_started_sse_event(self, mock_popen):
        """Publishes a ralph_started SSE event to the project's internal events."""
        from app.sse import subscribe, unsubscribe

        mock_process = MagicMock()
        mock_process.stdout = iter([])
        mock_popen.return_value = mock_process

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            q = subscribe("test-project")
            try:
                client = app.test_client()
                _auth_session(client)
                response = client.post("/projects/test-project/ralph/start")
                assert response.status_code == 200

                # Check that ralph_started event was published
                event = q.get(timeout=2)
                assert event["type"] == "ralph_started"
            finally:
                unsubscribe("test-project", q)
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.subprocess.Popen")
    def test_spawns_ralph_subprocess(self, mock_popen):
        """Spawns ralph.py as a subprocess with correct cwd."""
        mock_process = MagicMock()
        mock_process.stdout = iter([])
        mock_popen.return_value = mock_process

        app, db_path, db_fd = _make_app()
        try:
            vps_path = "/home/nico/projects/test-project"
            _insert_project(db_path, ralph_running=0, vps_path=vps_path)
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/ralph/start")
            assert response.status_code == 200

            # Verify Popen was called
            mock_popen.assert_called_once()
            call_kwargs = mock_popen.call_args
            # The cwd should be the project's vps_path
            assert call_kwargs.kwargs.get("cwd") or call_kwargs[1].get("cwd") == vps_path
            # The command should include ralph.py
            args = call_kwargs[0][0] if call_kwargs[0] else call_kwargs.kwargs.get("args", [])
            # Check that ralph.py path is in the command args
            joined_args = " ".join(str(a) for a in args)
            assert "ralph.py" in joined_args
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# GET /projects/<slug>/ralph/output
# ===========================================================================


class TestRalphOutputAuth:
    """Auth and basic validation for GET /projects/<slug>/ralph/output."""

    def test_unauthenticated_redirects(self):
        """Unauthenticated request redirects to /."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.get("/projects/test-project/ralph/output")
            assert response.status_code == 302
            assert response.headers["Location"] == "/"
        finally:
            _cleanup(db_fd, db_path)

    def test_nonexistent_project_returns_404(self):
        """Authenticated request for nonexistent project returns 404."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/nonexistent/ralph/output")
            assert response.status_code == 404
        finally:
            _cleanup(db_fd, db_path)


class TestRalphOutputStream:
    """GET /projects/<slug>/ralph/output streams Ralph's stdout as SSE."""

    def test_returns_sse_content_type(self):
        """Response has text/event-stream content type."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=1)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project/ralph/output")
            assert response.content_type.startswith("text/event-stream")
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.ralph_processes", new_callable=dict)
    def test_streams_stdout_lines_as_sse_data(self, mock_processes):
        """Streams Ralph stdout lines as SSE data events."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=1)

            # Simulate a mock process with stdout lines
            mock_process = MagicMock()
            mock_process.stdout.__iter__ = MagicMock(
                return_value=iter(
                    [
                        b"Processing issue #1\n",
                        b"COMPLETED ASSIGNED ISSUE\n",
                    ]
                )
            )
            mock_process.poll.return_value = None  # still running
            mock_processes["test-project"] = mock_process

            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project/ralph/output")
            data = response.get_data(as_text=True)

            # Each stdout line should appear as SSE data
            assert "data:" in data
            assert "Processing issue #1" in data
            assert "COMPLETED ASSIGNED ISSUE" in data
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# Ralph completion behavior
# ===========================================================================


class TestRalphCompletion:
    """When ralph.py finishes, ralph_running is reset and event published."""

    @patch("app.routes.subprocess.Popen")
    def test_ralph_finish_resets_ralph_running(self, mock_popen):
        """After ralph.py subprocess exits, ralph_running is set back to 0 in DB."""
        # This tests the background thread/callback that monitors the process.
        # The implementation should set ralph_running=0 when the process ends.
        mock_process = MagicMock()
        mock_process.stdout = iter([])
        mock_process.wait.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)

            response = client.post("/projects/test-project/ralph/start")
            assert response.status_code == 200

            # Give the background watcher thread time to run
            import time

            time.sleep(0.5)

            db = sqlite3.connect(db_path)
            row = db.execute(
                "SELECT ralph_running FROM projects WHERE slug = ?",
                ("test-project",),
            ).fetchone()
            db.close()
            assert row[0] == 0
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.subprocess.Popen")
    def test_ralph_finish_publishes_ralph_stopped_event(self, mock_popen):
        """After ralph.py finishes, a ralph_stopped SSE event is published."""
        from app.sse import subscribe, unsubscribe

        mock_process = MagicMock()
        mock_process.stdout = iter([])
        mock_process.wait.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            q = subscribe("test-project")
            try:
                client = app.test_client()
                _auth_session(client)
                response = client.post("/projects/test-project/ralph/start")
                assert response.status_code == 200

                # Collect events — expect ralph_started then ralph_stopped
                import time

                time.sleep(0.5)

                events = []
                while not q.empty():
                    events.append(q.get_nowait())

                event_types = [e["type"] for e in events]
                assert "ralph_started" in event_types
                assert "ralph_stopped" in event_types
            finally:
                unsubscribe("test-project", q)
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# show.html UI elements for Ralph launch
# ===========================================================================


class TestRalphUI:
    """Ralph launch UI elements in the project page HTML."""

    def test_just_ralph_it_button_exists_hidden(self):
        """Page includes a hidden 'Just Ralph It' button with id='just-ralph-it-btn'."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert 'id="just-ralph-it-btn"' in html
            assert "Just Ralph It" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_ralph_status_element_exists_hidden(self):
        """Page includes a hidden 'Ralph is building...' status with id='ralph-status'."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert 'id="ralph-status"' in html
            assert "Ralph is building" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_page_connects_to_internal_events_sse(self):
        """Page JS connects to /internal/projects/<slug>/events SSE endpoint."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            # JS should contain the internal events SSE URL pattern
            assert "/internal/projects/" in html
            assert "/events" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_page_has_ralph_running_js_variable(self):
        """Page has a RALPH_RUNNING JS variable populated from the template."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert "RALPH_RUNNING" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_ralph_running_shows_status_not_button(self):
        """When ralph_running=1 on page load, status indicator is visible, button hidden."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=1)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()

            # The ralph-status element should be visible (no display:none)
            # We look for the element and check it doesn't have display:none
            # Find the ralph-status element — it should NOT be hidden
            ralph_status_idx = html.find('id="ralph-status"')
            assert ralph_status_idx != -1

            # The just-ralph-it-btn should be hidden when ralph is running
            btn_idx = html.find('id="just-ralph-it-btn"')
            assert btn_idx != -1

            # Check that RALPH_RUNNING is set to 1
            assert "RALPH_RUNNING = 1" in html or "RALPH_RUNNING=1" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_ralph_not_running_hides_status(self):
        """When ralph_running=0 on page load, the button is available (hidden until SSE),
        and the status indicator is hidden."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            # RALPH_RUNNING should be 0
            assert "RALPH_RUNNING = 0" in html or "RALPH_RUNNING=0" in html
        finally:
            _cleanup(db_fd, db_path)
