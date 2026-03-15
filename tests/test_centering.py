"""Tests for UI centering via .container class.

The .container class in style.css centers content with max-width: 800px.
Pages that extend base.html get the container wrapper by default.
The project show page overrides {% block body %} for full-width layout.
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


def _insert_project(db_path, slug="test-project", name="test-project"):
    """Insert a project directly into the DB."""
    db = sqlite3.connect(db_path)
    db.execute(
        "INSERT INTO projects (name, slug) VALUES (?, ?)",
        (name, slug),
    )
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# 1. CSS file contains .container class with max-width and margin: 0 auto
# ---------------------------------------------------------------------------


class TestContainerCssClass:
    """.container class must exist in style.css with centering properties."""

    def test_css_has_container_class(self):
        """style.css contains a .container selector."""
        app = create_app()
        css_path = os.path.join(app.static_folder, "style.css")
        with open(css_path) as f:
            css = f.read()
        assert ".container" in css

    def test_container_has_max_width(self):
        """The .container class defines max-width."""
        app = create_app()
        css_path = os.path.join(app.static_folder, "style.css")
        with open(css_path) as f:
            css = f.read()
        assert "max-width" in css

    def test_container_has_margin_auto(self):
        """The .container class defines margin: 0 auto for centering."""
        app = create_app()
        css_path = os.path.join(app.static_folder, "style.css")
        with open(css_path) as f:
            css = f.read()
        assert "margin: 0 auto" in css


# ---------------------------------------------------------------------------
# 2. Landing page has content wrapped in <div class="container">
# ---------------------------------------------------------------------------


class TestLandingPageContainer:
    """GET / should have a <div class="container"> wrapper."""

    def test_landing_page_has_container_div(self):
        """The landing page HTML contains <div class="container">."""
        app = create_app()
        client = app.test_client()
        response = client.get("/")
        html = response.data.decode()
        assert '<div class="container">' in html


# ---------------------------------------------------------------------------
# 3. Projects list has content wrapped in <div class="container">
# ---------------------------------------------------------------------------


class TestProjectsListContainer:
    """GET /projects should have a <div class="container"> wrapper."""

    def test_projects_list_has_container_div(self):
        """The projects list page HTML contains <div class="container">."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects")
            html = response.data.decode()
            assert '<div class="container">' in html
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# 4. New project form has content wrapped in <div class="container">
# ---------------------------------------------------------------------------


class TestNewProjectContainer:
    """GET /projects/new should have a <div class="container"> wrapper."""

    def test_new_project_has_container_div(self):
        """The new project page HTML contains <div class="container">."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/new")
            html = response.data.decode()
            assert '<div class="container">' in html
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# 5. Project show page does NOT have <div class="container">
# ---------------------------------------------------------------------------


class TestProjectShowNoContainer:
    """GET /projects/<slug> should NOT have a <div class="container"> wrapper
    because it overrides {% block body %} for full-width layout."""

    def test_project_show_no_container_div(self):
        """The project show page does NOT contain <div class="container">."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert '<div class="container">' not in html
        finally:
            _cleanup(db_fd, db_path)
