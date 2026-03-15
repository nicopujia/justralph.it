"""Tests for the projects list page (TDD — written before implementation).

Feature: GET /projects
- Shows all projects belonging to the authenticated user
- Each project shows its name and links to /projects/:slug
- Includes a "New Project" button linking to /projects/new
- Auth-gated (unauthenticated → redirect to /)
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
        sess["installation_id"] = "12345"
        sess["installation_token"] = "ghs_test_token"
        sess["token_expires_at"] = "2026-03-15T12:00:00Z"


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
# GET /projects — projects list page
# ---------------------------------------------------------------------------


class TestProjectsList:
    """GET /projects — render the projects list page."""

    def test_unauthenticated_redirects_to_index(self):
        """Unauthenticated user is redirected to /."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.get("/projects")
            assert response.status_code == 302
            assert response.headers["Location"] == "/"
        finally:
            _cleanup(db_fd, db_path)

    def test_authenticated_returns_200(self):
        """Authenticated user sees the projects list (200 OK)."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects")
            assert response.status_code == 200
        finally:
            _cleanup(db_fd, db_path)

    def test_shows_new_project_button(self):
        """Response HTML contains a link to /projects/new with text 'New Project'."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects")
            html = response.data.decode()
            assert 'href="/projects/new"' in html
            assert "New Project" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_shows_project_name(self):
        """Inserted project name appears in the response HTML."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, name="my-awesome-app", slug="my-awesome-app")
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects")
            html = response.data.decode()
            assert "my-awesome-app" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_project_links_to_show_page(self):
        """Inserted project has a link to /projects/<slug>."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, name="my-project", slug="my-project")
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects")
            html = response.data.decode()
            assert 'href="/projects/my-project"' in html
        finally:
            _cleanup(db_fd, db_path)

    def test_shows_multiple_projects(self):
        """Multiple inserted projects all appear in the response HTML."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, name="alpha-project", slug="alpha-project")
            _insert_project(db_path, name="beta-project", slug="beta-project")
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects")
            html = response.data.decode()
            assert "alpha-project" in html
            assert "beta-project" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_empty_state_shows_no_projects(self):
        """With no projects in the DB, the page still returns 200 (no crash)."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects")
            assert response.status_code == 200
        finally:
            _cleanup(db_fd, db_path)

    def test_page_title(self):
        """Page title contains 'Projects'."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects")
            html = response.data.decode()
            # Check within <title> tag
            assert "<title>" in html.lower()
            title_start = html.lower().index("<title>")
            title_end = html.lower().index("</title>")
            title_content = html[title_start:title_end]
            assert "Projects" in title_content or "projects" in title_content.lower()
        finally:
            _cleanup(db_fd, db_path)
