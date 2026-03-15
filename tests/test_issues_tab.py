"""Tests for the Issues tab: beads visualization (TDD — written before implementation).

Feature: Issues tab in /projects/:slug
- bdui sidecar starts with --host 0.0.0.0 so the browser can connect
- bdui_port is rendered into the page so frontend JS can connect to bdui's WebSocket
- Issues tab has an issues-list container for JS to render into
- Placeholder text shown when no issues exist
"""

import os
import sqlite3
import tempfile
from unittest.mock import patch

from app import create_app

# ---------------------------------------------------------------------------
# Helpers
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


def _insert_project(db_path, name="test-project", slug="test-project", status="draft", bdui_port=None):
    """Insert a project directly into the DB."""
    db = sqlite3.connect(db_path)
    db.execute(
        "INSERT INTO projects (name, slug, status, bdui_port) VALUES (?, ?, ?, ?)",
        (name, slug, status, bdui_port),
    )
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Issues tab — backend HTML assertions
# ---------------------------------------------------------------------------


class TestIssuesTab:
    """Issues tab content rendered by the server."""

    def test_bdui_port_in_page(self):
        """The project's bdui_port value is rendered into the page so frontend JS can connect."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, bdui_port=9876)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert "9876" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_issues_placeholder_text(self):
        """Placeholder text is shown when no issues exist."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert "Continue chatting to let Ralphy create the spec" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_issues_container_has_id(self):
        """There is an element with id='issues-list' inside issues-content for JS to render into."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert 'id="issues-list"' in html
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# bdui start command
# ---------------------------------------------------------------------------


class TestBduiStartCommand:
    """The start_bdui function passes --host 0.0.0.0 to the bdui command."""

    def test_bdui_starts_with_host_flag(self):
        """start_bdui passes --host 0.0.0.0 so the browser can connect from outside."""
        with patch("app.projects.subprocess.Popen") as mock_popen:
            from app.projects import start_bdui

            start_bdui("/tmp/fake-project", 9876)

            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]  # positional arg: the command list
            assert "--host" in args
            assert "0.0.0.0" in args
