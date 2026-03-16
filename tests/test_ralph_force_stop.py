"""Tests for the Ralph force-stop feature (TDD — written before implementation).

Feature: Force Stop kills Ralph immediately and hard resets the repo to origin.

- POST /projects/<slug>/ralph/force-stop kills the ralph.py process (SIGKILL),
  runs `git reset --hard origin/main && git clean -fd` in the project directory,
  sets ralph_running=0 in DB, publishes ralph_stopped SSE event with
  reason="force_stopped", and returns {"status": "force_stopped"}.
- The show.html page has a #ralph-force-stop-btn, a forceStopRalph() JS function,
  a confirmation dialog with id="force-stop-dialog", and handles the
  ralph_stopped(reason=force_stopped) event in the terminal.

Routes:
- POST /projects/<slug>/ralph/force-stop — kill process, reset repo (auth-gated)

UI elements (show.html):
- #ralph-force-stop-btn  — force stop button, visible when Ralph is running
- forceStopRalph() JS    — shows confirmation dialog, POSTs to force-stop endpoint
- #force-stop-dialog     — confirmation dialog with warning text
- JS handles ralph_stopped with reason "force_stopped" (shows message in terminal)
"""

import os
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch

from app import create_app
from app.sse import subscribe, unsubscribe

# ---------------------------------------------------------------------------
# Helpers (same pattern as test_ralph_stop.py)
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
        sess["github_token"] = "gho_test_token"


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
# POST /projects/<slug>/ralph/force-stop — auth & validation
# ===========================================================================


class TestRalphForceStopAuth:
    """Auth gating and basic validation for POST /projects/<slug>/ralph/force-stop."""

    def test_unauthenticated_redirects(self):
        """Unauthenticated request redirects to /."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.post("/projects/test-project/ralph/force-stop")
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
            response = client.post("/projects/nonexistent/ralph/force-stop")
            assert response.status_code == 404
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# POST /projects/<slug>/ralph/force-stop — conflict (not running)
# ===========================================================================


class TestRalphForceStopConflict:
    """POST /projects/<slug>/ralph/force-stop returns 409 when Ralph is not running."""

    def test_returns_409_if_ralph_not_running(self):
        """Returns 409 Conflict when ralph_running is 0 (Ralph is not running)."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/ralph/force-stop")
            assert response.status_code == 409
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# POST /projects/<slug>/ralph/force-stop — success
# ===========================================================================


class TestRalphForceStopSuccess:
    """POST /projects/<slug>/ralph/force-stop succeeds when Ralph is running."""

    @patch("app.routes.subprocess.run")
    def test_kills_ralph_process_with_sigkill(self, mock_subprocess_run):
        """Calls proc.kill() (SIGKILL) on the ralph process."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=1)
            mock_proc = MagicMock()
            with app.app_context():
                from app.routes import ralph_processes

                ralph_processes["test-project"] = mock_proc

            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/ralph/force-stop")
            assert response.status_code == 200

            # proc.kill() should have been called (sends SIGKILL)
            mock_proc.kill.assert_called_once()
        finally:
            # Clean up ralph_processes
            from app.routes import ralph_processes

            ralph_processes.pop("test-project", None)
            _cleanup(db_fd, db_path)

    @patch("app.routes.subprocess.run")
    def test_runs_git_reset_in_project_directory(self, mock_subprocess_run):
        """Runs git reset --hard origin/main && git clean -fd in the project's vps_path."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=1, vps_path="/home/nico/projects/test-project")
            mock_proc = MagicMock()
            with app.app_context():
                from app.routes import ralph_processes

                ralph_processes["test-project"] = mock_proc

            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/ralph/force-stop")
            assert response.status_code == 200

            # subprocess.run should have been called with git reset command
            mock_subprocess_run.assert_called_once()
            call_args = mock_subprocess_run.call_args
            cmd = call_args[0][0] if call_args[0] else call_args[1].get("args")
            # The command should contain git reset --hard origin/main && git clean -fd
            if isinstance(cmd, str):
                assert "git reset --hard origin/main" in cmd
                assert "git clean -fd" in cmd
            else:
                cmd_str = " ".join(cmd)
                assert "git reset --hard origin/main" in cmd_str
                assert "git clean -fd" in cmd_str
            # Should run in the project directory
            assert call_args[1].get("cwd") == "/home/nico/projects/test-project" or (
                len(call_args) > 1 and call_args[1].get("cwd") == "/home/nico/projects/test-project"
            )
        finally:
            from app.routes import ralph_processes

            ralph_processes.pop("test-project", None)
            _cleanup(db_fd, db_path)

    @patch("app.routes.subprocess.run")
    def test_sets_ralph_running_to_zero_in_db(self, mock_subprocess_run):
        """Sets ralph_running=0 in the database."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=1)
            mock_proc = MagicMock()
            with app.app_context():
                from app.routes import ralph_processes

                ralph_processes["test-project"] = mock_proc

            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/ralph/force-stop")
            assert response.status_code == 200

            # Verify DB was updated
            db = sqlite3.connect(db_path)
            row = db.execute("SELECT ralph_running FROM projects WHERE slug = ?", ("test-project",)).fetchone()
            db.close()
            assert row[0] == 0
        finally:
            from app.routes import ralph_processes

            ralph_processes.pop("test-project", None)
            _cleanup(db_fd, db_path)

    @patch("app.routes.subprocess.run")
    def test_publishes_ralph_stopped_sse_event_with_force_stopped_reason(self, mock_subprocess_run):
        """Publishes a ralph_stopped SSE event with reason='force_stopped'."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=1)
            mock_proc = MagicMock()
            with app.app_context():
                from app.routes import ralph_processes

                ralph_processes["test-project"] = mock_proc

            q = subscribe("test-project")
            try:
                client = app.test_client()
                _auth_session(client)
                response = client.post("/projects/test-project/ralph/force-stop")
                assert response.status_code == 200

                # Check that ralph_stopped event was published with reason="force_stopped"
                event = q.get(timeout=2)
                assert event["type"] == "ralph_stopped"
                assert event["data"]["reason"] == "force_stopped"
            finally:
                unsubscribe("test-project", q)
        finally:
            from app.routes import ralph_processes

            ralph_processes.pop("test-project", None)
            _cleanup(db_fd, db_path)

    @patch("app.routes.subprocess.run")
    def test_returns_200_with_force_stopped_status(self, mock_subprocess_run):
        """Returns 200 with JSON {"status": "force_stopped"}."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=1)
            mock_proc = MagicMock()
            with app.app_context():
                from app.routes import ralph_processes

                ralph_processes["test-project"] = mock_proc

            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/ralph/force-stop")
            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "force_stopped"
        finally:
            from app.routes import ralph_processes

            ralph_processes.pop("test-project", None)
            _cleanup(db_fd, db_path)

    @patch("app.routes.subprocess.run")
    def test_removes_process_from_ralph_processes(self, mock_subprocess_run):
        """Removes the process from the ralph_processes dict after force stop."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=1)
            mock_proc = MagicMock()
            with app.app_context():
                from app.routes import ralph_processes

                ralph_processes["test-project"] = mock_proc

            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/ralph/force-stop")
            assert response.status_code == 200

            # Process should be removed from ralph_processes
            from app.routes import ralph_processes

            assert "test-project" not in ralph_processes
        finally:
            from app.routes import ralph_processes

            ralph_processes.pop("test-project", None)
            _cleanup(db_fd, db_path)

    @patch("app.routes.subprocess.run")
    def test_publishes_force_stopped_message(self, mock_subprocess_run):
        """The ralph_stopped event data includes 'Force stopped and reset to origin' message."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=1)
            mock_proc = MagicMock()
            with app.app_context():
                from app.routes import ralph_processes

                ralph_processes["test-project"] = mock_proc

            q = subscribe("test-project")
            try:
                client = app.test_client()
                _auth_session(client)
                response = client.post("/projects/test-project/ralph/force-stop")
                assert response.status_code == 200

                event = q.get(timeout=2)
                assert event["type"] == "ralph_stopped"
                assert event["data"]["reason"] == "force_stopped"
                assert event["data"]["message"] == "Force stopped and reset to origin"
            finally:
                unsubscribe("test-project", q)
        finally:
            from app.routes import ralph_processes

            ralph_processes.pop("test-project", None)
            _cleanup(db_fd, db_path)


# ===========================================================================
# show.html UI elements for Ralph force-stop
# ===========================================================================


class TestRalphForceStopUI:
    """Ralph force-stop UI elements in the project page HTML."""

    def test_force_stop_button_exists(self):
        """Page includes a force stop button with id='ralph-force-stop-btn'."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert 'id="ralph-force-stop-btn"' in html
        finally:
            _cleanup(db_fd, db_path)

    def test_force_stop_button_hidden_by_default(self):
        """When ralph_running=0, the force stop button has display:none."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            # Find the force stop button and verify it's hidden
            btn_idx = html.find('id="ralph-force-stop-btn"')
            assert btn_idx != -1
            # Look at the full tag (from opening < to closing >) for display: none
            tag_start = html.rfind("<", 0, btn_idx)
            tag_end = html.find(">", btn_idx)
            tag_snippet = html[tag_start : tag_end + 1]
            assert "display: none" in tag_snippet or "display:none" in tag_snippet
        finally:
            _cleanup(db_fd, db_path)

    def test_force_stop_button_visible_when_ralph_running(self):
        """When ralph_running=1 on page load, the force stop button is visible (not hidden)."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=1)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            # The page JS should show the force stop button when RALPH_RUNNING is true.
            # We check that there's JS logic to show #ralph-force-stop-btn when RALPH_RUNNING is true.
            assert "RALPH_RUNNING = 1" in html or "RALPH_RUNNING=1" in html
            assert "ralph-force-stop-btn" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_page_has_force_stop_ralph_js_function(self):
        """Page JS defines a forceStopRalph() function."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert "forceStopRalph" in html
            # Should include the function definition
            assert "function forceStopRalph" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_confirmation_dialog_exists(self):
        """Page includes a confirmation dialog with id='force-stop-dialog'."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert 'id="force-stop-dialog"' in html
        finally:
            _cleanup(db_fd, db_path)

    def test_confirmation_dialog_contains_warning_text(self):
        """Confirmation dialog contains the exact warning text."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            expected_text = "This will immediately kill Ralph and hard reset the repo to match origin. Any uncommitted changes will be lost. Are you sure?"
            assert expected_text in html
        finally:
            _cleanup(db_fd, db_path)

    def test_page_handles_ralph_stopped_force_stopped_reason(self):
        """Page JS handles ralph_stopped event with reason='force_stopped' to show message in terminal."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            # The JS should check for reason === 'force_stopped' in the ralph_stopped handler
            assert "'force_stopped'" in html or '"force_stopped"' in html
            # And should display the terminal message
            assert "Force stopped and reset to origin" in html
        finally:
            _cleanup(db_fd, db_path)
