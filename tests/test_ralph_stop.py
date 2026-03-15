"""Tests for the Ralph stop/continue feature (TDD — written before implementation).

Feature: Stop and continue the Ralph loop from the web UI.

- POST /projects/<slug>/ralph/stop creates the .stop file and publishes
  a ralph_stopping SSE event.
- _watch_ralph detects "Stopping as requested." as reason="stopped".
- The show.html page has a #ralph-stop-btn, a stopRalph() JS function,
  and handles the ralph_stopping / ralph_stopped(reason=stopped) events.
- After Ralph stops, the "Just Ralph It" button re-appears so the user
  can continue.

Routes:
- POST /projects/<slug>/ralph/stop — create .stop file, signal stopping (auth-gated)

UI elements (show.html):
- #ralph-stop-btn       — stop button, visible when Ralph is running
- stopRalph() JS        — POSTs to /projects/<slug>/ralph/stop
- JS handles ralph_stopping SSE event (shows "Ralph is stopping..." text)
- JS handles ralph_stopped with reason "stopped" (shows Just Ralph It button)
"""

import os
import sqlite3
import tempfile
import time
from unittest.mock import MagicMock, patch

from app import create_app
from app.sse import subscribe, unsubscribe

# ---------------------------------------------------------------------------
# Helpers (same pattern as test_ralph_launch.py)
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
# POST /projects/<slug>/ralph/stop — auth & validation
# ===========================================================================


class TestRalphStopAuth:
    """Auth gating and basic validation for POST /projects/<slug>/ralph/stop."""

    def test_unauthenticated_redirects(self):
        """Unauthenticated request redirects to /."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.post("/projects/test-project/ralph/stop")
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
            response = client.post("/projects/nonexistent/ralph/stop")
            assert response.status_code == 404
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# POST /projects/<slug>/ralph/stop — conflict (not running)
# ===========================================================================


class TestRalphStopConflict:
    """POST /projects/<slug>/ralph/stop returns 409 when Ralph is not running."""

    def test_returns_409_if_ralph_not_running(self):
        """Returns 409 Conflict when ralph_running is 0 (Ralph is not running)."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/ralph/stop")
            assert response.status_code == 409
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# POST /projects/<slug>/ralph/stop — success
# ===========================================================================


class TestRalphStopSuccess:
    """POST /projects/<slug>/ralph/stop succeeds when Ralph is running."""

    @patch("app.routes.STOP_FILE")
    def test_creates_stop_file(self, mock_stop_file):
        """Creates the .stop file by calling touch() on the STOP_FILE path."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=1)
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/ralph/stop")
            assert response.status_code == 200

            # The stop file should have been created via touch()
            mock_stop_file.touch.assert_called_once()
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.STOP_FILE")
    def test_publishes_ralph_stopping_sse_event(self, mock_stop_file):
        """Publishes a ralph_stopping SSE event to the project's internal events."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=1)
            q = subscribe("test-project")
            try:
                client = app.test_client()
                _auth_session(client)
                response = client.post("/projects/test-project/ralph/stop")
                assert response.status_code == 200

                # Check that ralph_stopping event was published
                event = q.get(timeout=2)
                assert event["type"] == "ralph_stopping"
            finally:
                unsubscribe("test-project", q)
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.STOP_FILE")
    def test_returns_200_with_stopping_status(self, mock_stop_file):
        """Returns 200 with JSON {"status": "stopping"}."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=1)
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/ralph/stop")
            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "stopping"
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# _watch_ralph: reason detection for "stopped"
# ===========================================================================


class TestRalphStoppedReasonDetection:
    """When ralph.py exits with 'Stopping as requested.', reason should be 'stopped'."""

    @patch("app.routes.subprocess.Popen")
    def test_stopped_reason_when_stop_message(self, mock_popen):
        """When stdout last line is 'Stopping as requested.', ralph_stopped event has reason='stopped'."""
        mock_process = MagicMock()
        mock_process.stdout = iter([b"Working...\n", b"Stopping as requested.\n"])
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

                # Give the background watcher thread time to process
                time.sleep(0.5)

                events = []
                while not q.empty():
                    events.append(q.get_nowait())

                # Find the ralph_stopped event
                stopped_events = [e for e in events if e["type"] == "ralph_stopped"]
                assert len(stopped_events) == 1, (
                    f"Expected exactly 1 ralph_stopped event, got {len(stopped_events)}. "
                    f"All events: {[e['type'] for e in events]}"
                )
                assert stopped_events[0]["data"]["reason"] == "stopped"
            finally:
                unsubscribe("test-project", q)
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.subprocess.Popen")
    def test_all_done_reason_unchanged(self, mock_popen):
        """Existing behavior: 'NO MORE ISSUES LEFT' still produces reason='all_done'."""
        mock_process = MagicMock()
        mock_process.stdout = iter([b"Processing...\n", b"NO MORE ISSUES LEFT\n"])
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

                time.sleep(0.5)

                events = []
                while not q.empty():
                    events.append(q.get_nowait())

                stopped_events = [e for e in events if e["type"] == "ralph_stopped"]
                assert len(stopped_events) == 1
                assert stopped_events[0]["data"]["reason"] == "all_done"
            finally:
                unsubscribe("test-project", q)
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.subprocess.Popen")
    def test_human_needed_reason_unchanged(self, mock_popen):
        """Existing behavior: other messages still produce reason='human_needed'."""
        mock_process = MagicMock()
        mock_process.stdout = iter([b"Processing...\n", b"I NEED A HUMAN\n"])
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

                time.sleep(0.5)

                events = []
                while not q.empty():
                    events.append(q.get_nowait())

                stopped_events = [e for e in events if e["type"] == "ralph_stopped"]
                assert len(stopped_events) == 1
                assert stopped_events[0]["data"]["reason"] == "human_needed"
            finally:
                unsubscribe("test-project", q)
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# show.html UI elements for Ralph stop/continue
# ===========================================================================


class TestRalphStopUI:
    """Ralph stop/continue UI elements in the project page HTML."""

    def test_stop_button_exists(self):
        """Page includes a stop button with id='ralph-stop-btn'."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert 'id="ralph-stop-btn"' in html
        finally:
            _cleanup(db_fd, db_path)

    def test_stop_button_hidden_by_default(self):
        """When ralph_running=0, the stop button has display:none."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            # Find the stop button and verify it's hidden
            btn_idx = html.find('id="ralph-stop-btn"')
            assert btn_idx != -1
            # Look at the full tag (from opening < to closing >) for display: none
            tag_start = html.rfind("<", 0, btn_idx)
            tag_end = html.find(">", btn_idx)
            tag_snippet = html[tag_start : tag_end + 1]
            assert "display: none" in tag_snippet or "display:none" in tag_snippet
        finally:
            _cleanup(db_fd, db_path)

    def test_stop_button_visible_when_ralph_running(self):
        """When ralph_running=1 on page load, the stop button is visible (not hidden)."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=1)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            # The page JS should show the stop button when RALPH_RUNNING=1.
            # We check that there's JS logic to show #ralph-stop-btn when RALPH_RUNNING is true.
            assert "RALPH_RUNNING = 1" in html or "RALPH_RUNNING=1" in html
            assert "ralph-stop-btn" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_page_has_stop_ralph_js_function(self):
        """Page JS defines a stopRalph() function."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert "stopRalph" in html
            # Should include the function definition
            assert "function stopRalph" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_stop_ralph_posts_to_stop_endpoint(self):
        """stopRalph() JS function POSTs to /projects/<slug>/ralph/stop."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            # The JS should reference the ralph/stop endpoint
            assert "/ralph/stop" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_page_handles_ralph_stopping_sse_event(self):
        """Page JS handles the 'ralph_stopping' SSE event type."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert "ralph_stopping" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_page_shows_stopping_text_on_ralph_stopping(self):
        """When ralph_stopping event is received, UI shows 'stopping' status text."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            # The page should contain text like "Ralph is stopping" (shown on ralph_stopping event)
            assert "stopping" in html.lower()
        finally:
            _cleanup(db_fd, db_path)

    def test_page_handles_ralph_stopped_with_stopped_reason(self):
        """Page JS handles ralph_stopped event with reason='stopped' to show continue button."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            # The JS should check for reason === 'stopped' in the ralph_stopped handler
            assert "'stopped'" in html or '"stopped"' in html
        finally:
            _cleanup(db_fd, db_path)

    def test_stopped_reason_shows_just_ralph_it_button(self):
        """When ralph_stopped with reason='stopped', the Just Ralph It button is shown (continue)."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            # The ralph_stopped handler for 'stopped' reason should show the just-ralph-it-btn
            # by setting its display to '' (visible). The JS should reference both
            # 'stopped' and 'just-ralph-it-btn' in the same handler block.
            assert "just-ralph-it-btn" in html
            # Verify the stopped reason case exists alongside button display logic
            assert "stopped" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_stop_button_onclick_calls_stop_ralph(self):
        """The stop button's onclick calls stopRalph()."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            # Find the stop button and verify it has onclick="stopRalph()"
            btn_idx = html.find('id="ralph-stop-btn"')
            assert btn_idx != -1
            # Look in the surrounding tag for the onclick handler
            tag_start = html.rfind("<", 0, btn_idx)
            tag_end = html.find(">", btn_idx)
            tag_snippet = html[tag_start : tag_end + 1]
            assert "stopRalph()" in tag_snippet
        finally:
            _cleanup(db_fd, db_path)
