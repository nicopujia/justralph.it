"""Tests for project deletion feature (TDD — written before implementation).

Feature: POST /projects/<slug>/delete
- Auth-gated (unauthenticated → redirect to /)
- Nonexistent project slug → 404
- Deletes GitHub repo via API (best-effort)
- Removes ~/projects/<project_name>/ from the VPS (best-effort)
- Kills ralph.py process if running
- Kills bdui sidecar on the project's port (best-effort)
- Deletes opencode session via API (best-effort)
- Removes push_subscriptions for the project from DB
- Removes the project record from DB
- Redirects to /projects
"""

import os
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch

from app import create_app

# ---------------------------------------------------------------------------
# Helpers (same pattern as other test files)
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


def _insert_project(db_path, name="test-project", slug="test-project", **kwargs):
    """Insert a project directly into the DB."""
    db = sqlite3.connect(db_path)
    cols = ["name", "slug"] + list(kwargs.keys())
    vals = [name, slug] + list(kwargs.values())
    placeholders = ", ".join("?" * len(vals))
    db.execute(f"INSERT INTO projects ({', '.join(cols)}) VALUES ({placeholders})", vals)
    db.commit()
    db.close()


def _insert_push_subscription(db_path, project_slug, subscription_json='{"endpoint":"https://example.com"}'):
    """Insert a push subscription for a project."""
    db = sqlite3.connect(db_path)
    db.execute(
        "INSERT INTO push_subscriptions (project_slug, subscription_json) VALUES (?, ?)",
        (project_slug, subscription_json),
    )
    db.commit()
    db.close()


def _get_project_by_slug(db_path, slug):
    """Fetch a single project row by slug."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    db.close()
    return row


def _get_push_subscriptions(db_path, project_slug):
    """Fetch all push subscriptions for a project."""
    db = sqlite3.connect(db_path)
    rows = db.execute(
        "SELECT * FROM push_subscriptions WHERE project_slug = ?",
        (project_slug,),
    ).fetchall()
    db.close()
    return rows


# ---------------------------------------------------------------------------
# POST /projects/<slug>/delete — Auth & basic validation
# ---------------------------------------------------------------------------


class TestDeleteProjectAuth:
    """Auth and basic validation for POST /projects/<slug>/delete."""

    def test_unauthenticated_redirects_to_index(self):
        """Unauthenticated POST /projects/<slug>/delete redirects to /."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.post("/projects/test-project/delete")
            assert response.status_code == 302
            assert response.headers["Location"] == "/"
        finally:
            _cleanup(db_fd, db_path)

    def test_nonexistent_project_returns_404(self):
        """Authenticated POST for a nonexistent slug returns 404."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/nonexistent/delete")
            assert response.status_code == 404
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# POST /projects/<slug>/delete — Route behavior (redirect, DB cleanup)
# ---------------------------------------------------------------------------


class TestDeleteProjectRoute:
    """POST /projects/<slug>/delete — successful deletion flow."""

    @patch("app.routes.delete_github_repo")
    @patch("app.routes.stop_bdui")
    @patch("app.routes.delete_opencode_session")
    @patch("app.routes.remove_vps_directory")
    def test_successful_delete_redirects_to_projects(self, mock_rm_vps, mock_del_oc, mock_stop_bdui, mock_del_gh):
        """Successful delete redirects to /projects."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/delete")
            assert response.status_code == 302
            assert response.headers["Location"] == "/projects"
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.delete_github_repo")
    @patch("app.routes.stop_bdui")
    @patch("app.routes.delete_opencode_session")
    @patch("app.routes.remove_vps_directory")
    def test_successful_delete_removes_db_record(self, mock_rm_vps, mock_del_oc, mock_stop_bdui, mock_del_gh):
        """After deletion, the project row is gone from the database."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            client.post("/projects/test-project/delete")

            row = _get_project_by_slug(db_path, "test-project")
            assert row is None
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.delete_github_repo")
    @patch("app.routes.stop_bdui")
    @patch("app.routes.delete_opencode_session")
    @patch("app.routes.remove_vps_directory")
    def test_successful_delete_removes_push_subscriptions(self, mock_rm_vps, mock_del_oc, mock_stop_bdui, mock_del_gh):
        """After deletion, push_subscriptions for this project are removed."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            _insert_push_subscription(db_path, "test-project")
            _insert_push_subscription(db_path, "test-project", '{"endpoint":"https://example2.com"}')

            client = app.test_client()
            _auth_session(client)
            client.post("/projects/test-project/delete")

            subs = _get_push_subscriptions(db_path, "test-project")
            assert len(subs) == 0
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# POST /projects/<slug>/delete — GitHub repo deletion
# ---------------------------------------------------------------------------


class TestDeleteProjectGitHub:
    """GitHub repo deletion during project delete."""

    @patch("app.routes.delete_github_repo")
    @patch("app.routes.stop_bdui")
    @patch("app.routes.delete_opencode_session")
    @patch("app.routes.remove_vps_directory")
    def test_github_repo_deleted(self, mock_rm_vps, mock_del_oc, mock_stop_bdui, mock_del_gh):
        """delete_github_repo is called with the project name and token."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, name="my-repo", slug="my-repo")
            client = app.test_client()
            _auth_session(client)
            client.post("/projects/my-repo/delete")

            mock_del_gh.assert_called_once_with("my-repo", "ghs_test_token")
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.remove_vps_directory")
    @patch("app.routes.delete_opencode_session")
    @patch("app.routes.stop_bdui")
    @patch("app.routes.delete_github_repo", side_effect=Exception("GitHub API error"))
    def test_github_delete_failure_still_continues(self, mock_del_gh, mock_stop_bdui, mock_del_oc, mock_rm_vps):
        """If GitHub DELETE fails, deletion still proceeds (best-effort)."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/delete")

            # Should still redirect successfully
            assert response.status_code == 302
            assert response.headers["Location"] == "/projects"
            # Project should still be removed from DB
            row = _get_project_by_slug(db_path, "test-project")
            assert row is None
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# POST /projects/<slug>/delete — Process cleanup (ralph, bdui)
# ---------------------------------------------------------------------------


class TestDeleteProjectProcesses:
    """Process cleanup during project delete."""

    @patch("app.routes.delete_github_repo")
    @patch("app.routes.stop_bdui")
    @patch("app.routes.delete_opencode_session")
    @patch("app.routes.remove_vps_directory")
    def test_ralph_process_killed(self, mock_rm_vps, mock_del_oc, mock_stop_bdui, mock_del_gh):
        """If ralph is running, process.kill() is called and entry removed from ralph_processes."""
        from app.routes import ralph_processes

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            mock_process = MagicMock()
            ralph_processes["test-project"] = mock_process

            client = app.test_client()
            _auth_session(client)
            client.post("/projects/test-project/delete")

            mock_process.kill.assert_called_once()
            assert "test-project" not in ralph_processes
        finally:
            ralph_processes.pop("test-project", None)
            _cleanup(db_fd, db_path)

    @patch("app.routes.delete_github_repo")
    @patch("app.routes.stop_bdui")
    @patch("app.routes.delete_opencode_session")
    @patch("app.routes.remove_vps_directory")
    def test_ralph_not_running_no_error(self, mock_rm_vps, mock_del_oc, mock_stop_bdui, mock_del_gh):
        """If ralph is not running for this project, no error occurs."""
        from app.routes import ralph_processes

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            # Ensure no ralph process for this slug
            ralph_processes.pop("test-project", None)

            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/delete")

            assert response.status_code == 302
            assert response.headers["Location"] == "/projects"
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.delete_github_repo")
    @patch("app.routes.delete_opencode_session")
    @patch("app.routes.remove_vps_directory")
    @patch("app.routes.stop_bdui")
    def test_bdui_process_killed(self, mock_stop_bdui, mock_rm_vps, mock_del_oc, mock_del_gh):
        """stop_bdui is called with the project's bdui_port."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, bdui_port=8765)
            client = app.test_client()
            _auth_session(client)
            client.post("/projects/test-project/delete")

            mock_stop_bdui.assert_called_once_with(8765)
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.delete_github_repo")
    @patch("app.routes.delete_opencode_session")
    @patch("app.routes.remove_vps_directory")
    @patch("app.routes.stop_bdui")
    def test_bdui_no_port_no_error(self, mock_stop_bdui, mock_rm_vps, mock_del_oc, mock_del_gh):
        """If bdui_port is None, stop_bdui is called with None and no error occurs."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)  # No bdui_port set → defaults to None
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/delete")

            mock_stop_bdui.assert_called_once_with(None)
            assert response.status_code == 302
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# POST /projects/<slug>/delete — Opencode session deletion
# ---------------------------------------------------------------------------


class TestDeleteProjectOpencode:
    """Opencode session deletion during project delete."""

    @patch("app.routes.delete_github_repo")
    @patch("app.routes.stop_bdui")
    @patch("app.routes.remove_vps_directory")
    @patch("app.routes.delete_opencode_session")
    def test_opencode_session_deleted(self, mock_del_oc, mock_rm_vps, mock_stop_bdui, mock_del_gh):
        """delete_opencode_session is called with the project's opencode_session_id."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, opencode_session_id="session-abc-123")
            client = app.test_client()
            _auth_session(client)
            client.post("/projects/test-project/delete")

            mock_del_oc.assert_called_once_with("session-abc-123")
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.delete_github_repo")
    @patch("app.routes.stop_bdui")
    @patch("app.routes.remove_vps_directory")
    @patch("app.routes.delete_opencode_session")
    def test_opencode_no_session_no_error(self, mock_del_oc, mock_rm_vps, mock_stop_bdui, mock_del_gh):
        """If opencode_session_id is None, delete_opencode_session is called with None and no error."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)  # No opencode_session_id → defaults to None
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/delete")

            mock_del_oc.assert_called_once_with(None)
            assert response.status_code == 302
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.remove_vps_directory")
    @patch("app.routes.stop_bdui")
    @patch("app.routes.delete_github_repo")
    @patch("app.routes.delete_opencode_session", side_effect=Exception("Opencode API error"))
    def test_opencode_delete_failure_still_continues(self, mock_del_oc, mock_del_gh, mock_stop_bdui, mock_rm_vps):
        """If opencode DELETE fails, deletion still proceeds (best-effort)."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, opencode_session_id="session-abc-123")
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/delete")

            assert response.status_code == 302
            assert response.headers["Location"] == "/projects"
            row = _get_project_by_slug(db_path, "test-project")
            assert row is None
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# POST /projects/<slug>/delete — VPS directory removal
# ---------------------------------------------------------------------------


class TestDeleteProjectVPSDirectory:
    """VPS directory removal during project delete."""

    @patch("app.routes.delete_github_repo")
    @patch("app.routes.stop_bdui")
    @patch("app.routes.delete_opencode_session")
    @patch("app.routes.remove_vps_directory")
    def test_vps_directory_removed(self, mock_rm_vps, mock_del_oc, mock_stop_bdui, mock_del_gh):
        """remove_vps_directory is called with the project's vps_path."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, vps_path="/home/nico/projects/test-project")
            client = app.test_client()
            _auth_session(client)
            client.post("/projects/test-project/delete")

            mock_rm_vps.assert_called_once_with("/home/nico/projects/test-project")
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.delete_github_repo")
    @patch("app.routes.stop_bdui")
    @patch("app.routes.delete_opencode_session")
    @patch("app.routes.remove_vps_directory")
    def test_vps_no_path_no_error(self, mock_rm_vps, mock_del_oc, mock_stop_bdui, mock_del_gh):
        """If vps_path is None, remove_vps_directory is called with None and no error."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)  # No vps_path → defaults to None
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/delete")

            mock_rm_vps.assert_called_once_with(None)
            assert response.status_code == 302
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.delete_github_repo")
    @patch("app.routes.stop_bdui")
    @patch("app.routes.delete_opencode_session")
    @patch("app.routes.remove_vps_directory", side_effect=Exception("Directory not found"))
    def test_vps_directory_missing_no_error(self, mock_rm_vps, mock_del_oc, mock_stop_bdui, mock_del_gh):
        """If the VPS directory doesn't exist, deletion still proceeds (best-effort)."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, vps_path="/home/nico/projects/test-project")
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/test-project/delete")

            assert response.status_code == 302
            assert response.headers["Location"] == "/projects"
            row = _get_project_by_slug(db_path, "test-project")
            assert row is None
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# GET /projects/<slug> — Delete button in the UI
# ---------------------------------------------------------------------------


class TestDeleteProjectUI:
    """Delete button UI elements on the project page."""

    @patch("app.routes.delete_github_repo")
    @patch("app.routes.stop_bdui")
    @patch("app.routes.delete_opencode_session")
    @patch("app.routes.remove_vps_directory")
    def test_project_page_has_delete_button(self, mock_rm_vps, mock_del_oc, mock_stop_bdui, mock_del_gh):
        """GET /projects/<slug> response HTML contains a delete button/form."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            # Should have a delete button or a form with a delete action
            assert "delete" in html.lower() or "Delete" in html
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.delete_github_repo")
    @patch("app.routes.stop_bdui")
    @patch("app.routes.delete_opencode_session")
    @patch("app.routes.remove_vps_directory")
    def test_delete_button_posts_to_correct_url(self, mock_rm_vps, mock_del_oc, mock_stop_bdui, mock_del_gh):
        """The delete form action points to /projects/<slug>/delete."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert "/projects/test-project/delete" in html
        finally:
            _cleanup(db_fd, db_path)
