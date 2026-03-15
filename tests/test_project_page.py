"""Tests for the project page layout (TDD — written before implementation).

Feature: GET /projects/:slug
- Two-panel layout: chat panel (left), tabbed panel (right)
- Three tabs: Spec (AGENTS.md placeholder), Issues (beads placeholder), Terminal (Ralph stdout placeholder)
- Auth-gated (unauthenticated → redirect to /)
- Nonexistent project slug → 404
- Chat panel always visible regardless of project state
"""

import os
import sqlite3
import tempfile

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
        sess["github_token"] = "gho_test_token"


def _insert_project(db_path, name="test-project", slug="test-project", status="draft"):
    """Insert a project directly into the DB."""
    db = sqlite3.connect(db_path)
    db.execute(
        "INSERT INTO projects (name, slug, status) VALUES (?, ?, ?)",
        (name, slug, status),
    )
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# GET /projects/:slug — project page layout
# ---------------------------------------------------------------------------


class TestGetProjectPage:
    """GET /projects/<slug> — render the two-panel project page."""

    def test_unauthenticated_redirects_to_index(self):
        """Unauthenticated user is redirected to /."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.get("/projects/some-slug")
            assert response.status_code == 302
            assert response.headers["Location"] == "/"
        finally:
            _cleanup(db_fd, db_path)

    def test_nonexistent_project_returns_404(self):
        """Authenticated request for a nonexistent slug returns 404."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/nonexistent")
            assert response.status_code == 404
        finally:
            _cleanup(db_fd, db_path)

    def test_authenticated_with_existing_project_returns_200(self):
        """Authenticated request for an existing project returns 200."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            assert response.status_code == 200
        finally:
            _cleanup(db_fd, db_path)

    def test_page_has_chat_panel(self):
        """Response HTML contains a chat panel element."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert 'id="chat-panel"' in html
        finally:
            _cleanup(db_fd, db_path)

    def test_page_has_tab_panel(self):
        """Response HTML contains a tabbed panel element."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert 'id="tab-panel"' in html
        finally:
            _cleanup(db_fd, db_path)

    def test_page_has_spec_tab(self):
        """Response HTML contains a Spec tab."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert "Spec" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_page_has_issues_tab(self):
        """Response HTML contains an Issues tab."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert "Issues" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_page_has_terminal_tab(self):
        """Response HTML contains a Terminal tab."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert "Terminal" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_page_has_two_panel_layout(self):
        """Both chat-panel and tab-panel are present in the HTML."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert 'id="chat-panel"' in html
            assert 'id="tab-panel"' in html
        finally:
            _cleanup(db_fd, db_path)

    def test_page_title_contains_project_name(self):
        """Page title includes the project name."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, name="my-cool-project", slug="my-cool-project")
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/my-cool-project")
            html = response.data.decode()
            assert "my-cool-project" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_spec_tab_content_exists(self):
        """There is a content area for the Spec tab."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert 'id="spec-content"' in html
        finally:
            _cleanup(db_fd, db_path)

    def test_issues_tab_content_exists(self):
        """There is a content area for the Issues tab."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert 'id="issues-content"' in html
        finally:
            _cleanup(db_fd, db_path)

    def test_terminal_tab_content_exists(self):
        """There is a content area for the Terminal tab."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert 'id="terminal-content"' in html
        finally:
            _cleanup(db_fd, db_path)
