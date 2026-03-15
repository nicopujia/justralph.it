"""Tests for the Spec tab — live AGENTS.md viewer (TDD — written before implementation).

Feature: GET /projects/<slug>/spec
- Returns rendered AGENTS.md content from the project's vps_path
- If AGENTS.md doesn't exist, returns placeholder message
- Auth-gated (unauthenticated → redirect to /)
- Nonexistent project slug → 404
- The project show page has HTMX polling attributes on the spec-content div
"""

import os
import shutil
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


def _cleanup(db_fd, db_path, tmp_dirs=None):
    os.close(db_fd)
    os.unlink(db_path)
    for d in tmp_dirs or []:
        shutil.rmtree(d, ignore_errors=True)


def _auth_session(client):
    """Set session vars to simulate an authenticated user."""
    with client.session_transaction() as sess:
        sess["user"] = "nicopujia"
        sess["github_token"] = "gho_test_token"


def _insert_project(db_path, name="test-project", slug="test-project", status="draft", vps_path=None):
    """Insert a project directly into the DB, with optional vps_path."""
    db = sqlite3.connect(db_path)
    db.execute(
        "INSERT INTO projects (name, slug, status, vps_path) VALUES (?, ?, ?, ?)",
        (name, slug, status, vps_path),
    )
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# GET /projects/<slug>/spec — spec endpoint
# ---------------------------------------------------------------------------


class TestSpecEndpoint:
    """GET /projects/<slug>/spec — returns rendered AGENTS.md content."""

    def test_spec_endpoint_unauthenticated_redirects(self):
        """Unauthenticated request to spec endpoint redirects to /."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.get("/projects/some-slug/spec")
            assert response.status_code == 302
            assert response.headers["Location"] == "/"
        finally:
            _cleanup(db_fd, db_path)

    def test_spec_endpoint_nonexistent_project_404(self):
        """Authenticated request for a nonexistent slug returns 404."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/nonexistent/spec")
            assert response.status_code == 404
        finally:
            _cleanup(db_fd, db_path)

    def test_spec_endpoint_no_agents_md_returns_placeholder(self):
        """When AGENTS.md doesn't exist at the project's vps_path, returns placeholder."""
        tmp_dir = tempfile.mkdtemp()
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, vps_path=tmp_dir)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project/spec")
            assert response.status_code == 200
            html = response.data.decode()
            assert "Continue chatting to let Ralphy create the spec" in html
        finally:
            _cleanup(db_fd, db_path, [tmp_dir])

    def test_spec_endpoint_with_agents_md_returns_content(self):
        """When AGENTS.md exists, returns its content rendered as HTML."""
        tmp_dir = tempfile.mkdtemp()
        agents_path = os.path.join(tmp_dir, "AGENTS.md")
        with open(agents_path, "w") as f:
            f.write("This is the project spec.")
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, vps_path=tmp_dir)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project/spec")
            assert response.status_code == 200
            html = response.data.decode()
            assert "This is the project spec." in html
            # Should NOT contain the placeholder
            assert "Continue chatting to let Ralphy create the spec" not in html
        finally:
            _cleanup(db_fd, db_path, [tmp_dir])

    def test_spec_endpoint_renders_markdown(self):
        """When AGENTS.md has markdown, the response contains rendered HTML."""
        tmp_dir = tempfile.mkdtemp()
        agents_path = os.path.join(tmp_dir, "AGENTS.md")
        with open(agents_path, "w") as f:
            f.write("# Heading\n\nSome **bold** text.")
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, vps_path=tmp_dir)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project/spec")
            assert response.status_code == 200
            html = response.data.decode()
            assert "<h1>Heading</h1>" in html
            assert "<strong>bold</strong>" in html
        finally:
            _cleanup(db_fd, db_path, [tmp_dir])

    def test_spec_content_updates_when_file_changes(self):
        """After AGENTS.md is updated, a subsequent fetch returns the new content."""
        tmp_dir = tempfile.mkdtemp()
        agents_path = os.path.join(tmp_dir, "AGENTS.md")
        with open(agents_path, "w") as f:
            f.write("Version 1")
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, vps_path=tmp_dir)
            client = app.test_client()
            _auth_session(client)

            # First fetch
            response1 = client.get("/projects/test-project/spec")
            html1 = response1.data.decode()
            assert "Version 1" in html1

            # Update the file
            with open(agents_path, "w") as f:
                f.write("Version 2")

            # Second fetch should reflect the update
            response2 = client.get("/projects/test-project/spec")
            html2 = response2.data.decode()
            assert "Version 2" in html2
            assert "Version 1" not in html2
        finally:
            _cleanup(db_fd, db_path, [tmp_dir])


class TestShowPageSpecPolling:
    """The project show page includes HTMX polling attributes for the spec tab."""

    def test_show_page_has_htmx_polling_on_spec_tab(self):
        """The spec-content div has hx-get and hx-trigger attributes for polling."""
        tmp_dir = tempfile.mkdtemp()
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, vps_path=tmp_dir)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            assert response.status_code == 200
            html = response.data.decode()
            # The spec-content div should poll the spec endpoint
            assert "hx-get" in html
            assert "/projects/test-project/spec" in html
            assert "hx-trigger" in html
            # Should poll on an interval (e.g. "every 3s")
            assert "every" in html.lower()
        finally:
            _cleanup(db_fd, db_path, [tmp_dir])
