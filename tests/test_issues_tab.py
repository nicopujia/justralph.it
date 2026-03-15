"""Tests for the Issues tab: read-only beads visualization.

Feature: Issues tab in /projects/:slug
- bdui sidecar binds to localhost (127.0.0.1) — NOT exposed to the internet
- A WebSocket proxy route at /projects/<slug>/bdui/ws forwards read-only messages
- Frontend JS connects through the proxy, not directly to bdui
- Issues tab has an issues-list container for JS to render into
- Placeholder text shown when no issues exist
- No interactive controls (edit/delete/create) in the Issues tab HTML
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
# bdui start command — binds to localhost, not 0.0.0.0
# ---------------------------------------------------------------------------


class TestBduiStartCommand:
    """The start_bdui function does NOT pass --host 0.0.0.0 (bdui defaults to 127.0.0.1)."""

    def test_bdui_starts_without_host_0000(self):
        """start_bdui must NOT bind to 0.0.0.0 — bdui defaults to 127.0.0.1."""
        with patch("app.projects.subprocess.Popen") as mock_popen:
            from app.projects import start_bdui

            start_bdui("/tmp/fake-project", 9876)

            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]  # positional arg: the command list
            assert "0.0.0.0" not in args

    def test_bdui_starts_with_port_flag(self):
        """start_bdui passes --port with the given port number."""
        with patch("app.projects.subprocess.Popen") as mock_popen:
            from app.projects import start_bdui

            start_bdui("/tmp/fake-project", 9876)

            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert "--port" in args
            assert "9876" in args


# ---------------------------------------------------------------------------
# WebSocket proxy route
# ---------------------------------------------------------------------------


class TestWsProxyRoute:
    """The /projects/<slug>/bdui/ws route exists and requires auth."""

    def test_ws_proxy_route_exists(self):
        """A non-WebSocket GET to the proxy URL returns 400 (not 404)."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, bdui_port=9876)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project/bdui/ws")
            # flask-sock returns 400 for non-WebSocket requests (not 404)
            assert response.status_code == 400
        finally:
            _cleanup(db_fd, db_path)

    def test_ws_proxy_unauthenticated_returns_400(self):
        """Unauthenticated requests to the WS proxy route get 400 (non-WS) — the WS handler itself checks auth."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, bdui_port=9876)
            client = app.test_client()
            # No auth session
            response = client.get("/projects/test-project/bdui/ws")
            # flask-sock rejects non-WS requests before the handler runs
            assert response.status_code == 400
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# Frontend JS — connects through proxy, not directly to bdui
# ---------------------------------------------------------------------------


class TestFrontendWsProxy:
    """Frontend JS must connect through the proxy, not directly to bdui."""

    def test_frontend_does_not_connect_directly_to_bdui_port(self):
        """show.html must NOT contain a direct WS connection to the bdui port."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, bdui_port=9876)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            # Must NOT have the old pattern of connecting directly via hostname:port
            assert "window.location.hostname + ':' + BDUI_PORT" not in html
        finally:
            _cleanup(db_fd, db_path)

    def test_frontend_connects_through_proxy_url(self):
        """show.html must connect via /projects/<slug>/bdui/ws proxy URL."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, bdui_port=9876)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert "/bdui/ws" in html
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# Issues tab is read-only — no interactive controls
# ---------------------------------------------------------------------------


class TestIssuesTabReadOnly:
    """The Issues tab HTML must not contain interactive controls for issues."""

    def test_no_edit_buttons_in_issues_tab(self):
        """Issues tab should not have edit buttons."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, bdui_port=9876)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            # Extract issues-content div content
            start = html.find('id="issues-content"')
            end = html.find('id="terminal-content"')
            issues_html = html[start:end] if start != -1 and end != -1 else ""
            # No form elements or edit/delete/create buttons in issues section
            assert "<form" not in issues_html.lower()
            assert "edit" not in issues_html.lower()
            assert "delete-issue" not in issues_html.lower()
            assert "create-issue" not in issues_html.lower()
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# WS proxy message filtering
# ---------------------------------------------------------------------------


class TestWsProxyAllowedTypes:
    """Only read-only WebSocket message types should be proxied to bdui."""

    def test_allowed_types_constant_exists(self):
        """The ALLOWED_WS_TYPES constant must exist in routes and contain expected types."""
        from app.routes import ALLOWED_WS_TYPES

        assert "subscribe-list" in ALLOWED_WS_TYPES
        assert "unsubscribe-list" in ALLOWED_WS_TYPES
        assert "pong" in ALLOWED_WS_TYPES

    def test_write_types_not_allowed(self):
        """Write operations must NOT be in ALLOWED_WS_TYPES."""
        from app.routes import ALLOWED_WS_TYPES

        assert "create-issue" not in ALLOWED_WS_TYPES
        assert "update-status" not in ALLOWED_WS_TYPES
        assert "edit-text" not in ALLOWED_WS_TYPES
        assert "delete-issue" not in ALLOWED_WS_TYPES
