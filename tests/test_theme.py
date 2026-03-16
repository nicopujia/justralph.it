"""Tests for global theme support (TDD — written before implementation).

Bug: CSS prefers-color-scheme is only in one template (projects/show.html
delete dialog).  It needs to be global across all pages.

Fix: A global CSS file app/static/style.css with CSS custom properties and
a @media (prefers-color-scheme: light) block, linked from base.html.
"""

import os
import re
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
# 1. base.html links to /static/style.css
# ---------------------------------------------------------------------------


class TestBaseTemplateLinksStylesheet:
    """base.html must include a <link> tag referencing /static/style.css."""

    def test_base_html_has_stylesheet_link(self):
        """The rendered index page (which extends base.html) includes a
        <link> to /static/style.css."""
        app = create_app({"TESTING": True})
        client = app.test_client()
        response = client.get("/")
        html = response.data.decode()
        assert 'href="/static/style.css"' in html

    def test_stylesheet_link_is_css_type(self):
        """The <link> tag uses rel="stylesheet"."""
        app = create_app({"TESTING": True})
        client = app.test_client()
        response = client.get("/")
        html = response.data.decode()
        # Find the link tag that references style.css
        assert 'rel="stylesheet"' in html


# ---------------------------------------------------------------------------
# 2. app/static/style.css exists and contains prefers-color-scheme
# ---------------------------------------------------------------------------


class TestStyleCssFileExists:
    """The file app/static/style.css must exist on disk and contain
    prefers-color-scheme."""

    def test_style_css_file_exists(self):
        """app/static/style.css exists on disk."""
        app = create_app({"TESTING": True})
        css_path = os.path.join(app.static_folder, "style.css")
        assert os.path.isfile(css_path), f"Expected {css_path} to exist"

    def test_style_css_contains_prefers_color_scheme(self):
        """app/static/style.css contains 'prefers-color-scheme'."""
        app = create_app({"TESTING": True})
        css_path = os.path.join(app.static_folder, "style.css")
        with open(css_path) as f:
            css = f.read()
        assert "prefers-color-scheme" in css


# ---------------------------------------------------------------------------
# 3. CSS file defines CSS custom properties on :root
# ---------------------------------------------------------------------------


class TestCssCustomProperties:
    """The CSS file must define CSS custom properties (variables) on :root."""

    def test_has_root_selector(self):
        """style.css contains a :root selector."""
        app = create_app({"TESTING": True})
        css_path = os.path.join(app.static_folder, "style.css")
        with open(css_path) as f:
            css = f.read()
        assert ":root" in css

    def test_defines_bg_primary_variable(self):
        """style.css defines --bg-primary custom property."""
        app = create_app({"TESTING": True})
        css_path = os.path.join(app.static_folder, "style.css")
        with open(css_path) as f:
            css = f.read()
        assert "--bg-primary" in css

    def test_defines_text_primary_variable(self):
        """style.css defines --text-primary custom property."""
        app = create_app({"TESTING": True})
        css_path = os.path.join(app.static_folder, "style.css")
        with open(css_path) as f:
            css = f.read()
        assert "--text-primary" in css


# ---------------------------------------------------------------------------
# 4. CSS file has @media (prefers-color-scheme: light) block
# ---------------------------------------------------------------------------


class TestLightModeMediaQuery:
    """The CSS file must have a @media (prefers-color-scheme: light) block."""

    def test_has_light_mode_media_query(self):
        """style.css has @media (prefers-color-scheme: light)."""
        app = create_app({"TESTING": True})
        css_path = os.path.join(app.static_folder, "style.css")
        with open(css_path) as f:
            css = f.read()
        assert "prefers-color-scheme: light" in css


# ---------------------------------------------------------------------------
# 5. Every page includes the global stylesheet (inherits from base.html)
# ---------------------------------------------------------------------------


class TestAllPagesIncludeStylesheet:
    """Every page must include the /static/style.css stylesheet link
    (inherited from base.html)."""

    def test_index_page_includes_stylesheet(self):
        """GET / includes /static/style.css."""
        app = create_app({"TESTING": True})
        client = app.test_client()
        response = client.get("/")
        html = response.data.decode()
        assert "/static/style.css" in html

    def test_projects_list_includes_stylesheet(self):
        """GET /projects includes /static/style.css."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects")
            html = response.data.decode()
            assert "/static/style.css" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_new_project_page_includes_stylesheet(self):
        """GET /projects/new includes /static/style.css."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/new")
            html = response.data.decode()
            assert "/static/style.css" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_project_show_page_includes_stylesheet(self):
        """GET /projects/<slug> includes /static/style.css."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert "/static/style.css" in html
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# 6. No hardcoded dark-mode background colors in inline style attributes
# ---------------------------------------------------------------------------


# Hardcoded dark-mode background colors that should be replaced with CSS vars.
_HARDCODED_BG_COLORS = ["#1a1a1a", "#2a2a2a", "#1e1e1e", "#111"]


class TestNoHardcodedDarkBackgrounds:
    """Inline style="" attributes must not contain hardcoded dark-mode
    background colors.  These should use CSS custom properties instead."""

    def _assert_no_hardcoded_bg_in_inline_styles(self, html):
        """Extract all style="..." attribute values and assert none of them
        contain a known dark-mode background color."""
        inline_styles = re.findall(r'style="([^"]*)"', html)
        for style_value in inline_styles:
            for color in _HARDCODED_BG_COLORS:
                assert color not in style_value, (
                    f'Found hardcoded dark background color {color} in inline style="{style_value}"'
                )

    def test_index_no_hardcoded_bg(self):
        """GET / has no hardcoded dark bg colors in inline styles."""
        app = create_app({"TESTING": True})
        client = app.test_client()
        response = client.get("/")
        self._assert_no_hardcoded_bg_in_inline_styles(response.data.decode())

    def test_projects_list_no_hardcoded_bg(self):
        """GET /projects has no hardcoded dark bg colors in inline styles."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects")
            self._assert_no_hardcoded_bg_in_inline_styles(response.data.decode())
        finally:
            _cleanup(db_fd, db_path)

    def test_new_project_no_hardcoded_bg(self):
        """GET /projects/new has no hardcoded dark bg colors in inline styles."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/new")
            self._assert_no_hardcoded_bg_in_inline_styles(response.data.decode())
        finally:
            _cleanup(db_fd, db_path)

    def test_project_show_no_hardcoded_bg(self):
        """GET /projects/<slug> has no hardcoded dark bg colors in inline styles."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            self._assert_no_hardcoded_bg_in_inline_styles(response.data.decode())
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# 7. No hardcoded dark-mode text colors in inline style attributes
# ---------------------------------------------------------------------------


# General text colors that need to switch between themes.
# Note: accent colors like #4fc3f7 or error colors like #ff5252 are fine.
_HARDCODED_TEXT_COLORS = ["#e0e0e0", "#888"]


class TestNoHardcodedDarkTextColors:
    """Inline style="" attributes must not use hardcoded dark-mode text
    colors for general text.  These should use CSS custom properties."""

    def _assert_no_hardcoded_text_in_inline_styles(self, html):
        """Extract all style="..." attribute values and assert none contain
        known dark-mode general text colors."""
        inline_styles = re.findall(r'style="([^"]*)"', html)
        for style_value in inline_styles:
            for color in _HARDCODED_TEXT_COLORS:
                assert color not in style_value, (
                    f'Found hardcoded dark text color {color} in inline style="{style_value}"'
                )

    def test_index_no_hardcoded_text(self):
        """GET / has no hardcoded dark text colors in inline styles."""
        app = create_app({"TESTING": True})
        client = app.test_client()
        response = client.get("/")
        self._assert_no_hardcoded_text_in_inline_styles(response.data.decode())

    def test_projects_list_no_hardcoded_text(self):
        """GET /projects has no hardcoded dark text colors in inline styles."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects")
            self._assert_no_hardcoded_text_in_inline_styles(response.data.decode())
        finally:
            _cleanup(db_fd, db_path)

    def test_new_project_no_hardcoded_text(self):
        """GET /projects/new has no hardcoded dark text colors in inline styles."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/new")
            self._assert_no_hardcoded_text_in_inline_styles(response.data.decode())
        finally:
            _cleanup(db_fd, db_path)

    def test_project_show_no_hardcoded_text(self):
        """GET /projects/<slug> has no hardcoded dark text colors in inline styles."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            self._assert_no_hardcoded_text_in_inline_styles(response.data.decode())
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# 8. base.html inline <style> block no longer contains hardcoded colors
# ---------------------------------------------------------------------------


class TestBaseTemplateNoInlineHardcodedColors:
    """base.html should no longer have hardcoded colors in an inline <style>
    block — styling should come from the linked CSS file."""

    def test_no_inline_style_block_with_hardcoded_colors(self):
        """The rendered HTML from base.html should not have a <style> block
        containing hardcoded background or text colors like #1a1a1a or
        #e0e0e0."""
        app = create_app({"TESTING": True})
        client = app.test_client()
        response = client.get("/")
        html = response.data.decode()
        # Extract all inline <style> blocks
        style_blocks = re.findall(r"<style>(.*?)</style>", html, re.DOTALL)
        all_hardcoded = _HARDCODED_BG_COLORS + _HARDCODED_TEXT_COLORS
        for block in style_blocks:
            for color in all_hardcoded:
                assert color not in block, (
                    f"Found hardcoded color {color} in inline <style> block "
                    f"in base template. Colors should be in /static/style.css "
                    f"using CSS custom properties."
                )
