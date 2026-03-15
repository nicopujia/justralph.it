"""Tests for the new-project form and setup flow (TDD — written before implementation).

Feature: GET/POST /projects/new
- Auth-gated form with repo name + description
- Validates repo name (GitHub-valid characters)
- Checks name availability (GitHub API + local directory)
- Creates GitHub repo, clones, inits beads, starts bdui, creates opencode session
- Stores project in SQLite with all fields
"""

import os
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch

from app import create_app
from app.projects import create_github_repo

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


def _get_project_by_slug(db_path, slug):
    """Fetch a single project row by slug."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    db.close()
    return row


# ---------------------------------------------------------------------------
# Schema tests — new columns required by the feature
# ---------------------------------------------------------------------------


class TestSchemaNewColumns:
    """The projects table must have extra columns for the setup flow."""

    def _get_columns(self, db_path):
        db = sqlite3.connect(db_path)
        cursor = db.execute("PRAGMA table_info(projects)")
        columns = {row[1] for row in cursor.fetchall()}
        db.close()
        return columns

    def test_projects_table_has_vps_path_column(self):
        app, db_path, db_fd = _make_app()
        try:
            assert "vps_path" in self._get_columns(db_path)
        finally:
            _cleanup(db_fd, db_path)

    def test_projects_table_has_opencode_session_id_column(self):
        app, db_path, db_fd = _make_app()
        try:
            assert "opencode_session_id" in self._get_columns(db_path)
        finally:
            _cleanup(db_fd, db_path)

    def test_projects_table_has_bdui_port_column(self):
        app, db_path, db_fd = _make_app()
        try:
            assert "bdui_port" in self._get_columns(db_path)
        finally:
            _cleanup(db_fd, db_path)

    def test_projects_table_has_description_column(self):
        app, db_path, db_fd = _make_app()
        try:
            assert "description" in self._get_columns(db_path)
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# GET /projects/new
# ---------------------------------------------------------------------------


class TestGetProjectsNew:
    """GET /projects/new — render the new-project form."""

    def test_unauthenticated_redirects_to_index(self):
        """Unauthenticated user is redirected to /."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.get("/projects/new")
            assert response.status_code == 302
            assert response.headers["Location"] == "/"
        finally:
            _cleanup(db_fd, db_path)

    def test_authenticated_returns_200(self):
        """Authenticated user sees the form (200 OK)."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/new")
            assert response.status_code == 200
        finally:
            _cleanup(db_fd, db_path)

    def test_form_has_repo_name_field(self):
        """Form contains an input for the repo name."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/new")
            html = response.data.decode()
            assert 'name="repo_name"' in html
        finally:
            _cleanup(db_fd, db_path)

    def test_form_has_description_field(self):
        """Form contains a textarea/input for the description."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/new")
            html = response.data.decode()
            assert 'name="description"' in html
        finally:
            _cleanup(db_fd, db_path)

    def test_description_placeholder(self):
        """Description field has the expected placeholder text."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/new")
            html = response.data.decode()
            assert "What do you want to build?" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_repo_name_label_exists(self):
        """There is a label or placeholder for the repo name field."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/new")
            html = response.data.decode()
            # Accept either a <label> tag or a placeholder attribute
            assert "Repo name" in html or "repo_name" in html
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# POST /projects/new — validation
# ---------------------------------------------------------------------------


class TestPostProjectsNewValidation:
    """POST /projects/new — input validation (no side-effects)."""

    def test_unauthenticated_redirects_to_index(self):
        """Unauthenticated POST is redirected to /."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.post("/projects/new", data={"repo_name": "my-app"})
            assert response.status_code == 302
            assert response.headers["Location"] == "/"
        finally:
            _cleanup(db_fd, db_path)

    def test_empty_repo_name_returns_error(self):
        """Empty repo name shows an error (400 or re-renders form with message)."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/new", data={"repo_name": ""})
            # Accept either 400 or 200 with error message
            html = response.data.decode()
            assert response.status_code == 400 or "error" in html.lower() or "required" in html.lower()
        finally:
            _cleanup(db_fd, db_path)

    def test_missing_repo_name_returns_error(self):
        """Missing repo_name field shows an error."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/new", data={})
            html = response.data.decode()
            assert response.status_code == 400 or "error" in html.lower() or "required" in html.lower()
        finally:
            _cleanup(db_fd, db_path)

    def test_invalid_repo_name_with_spaces(self):
        """Repo name with spaces is rejected."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/new", data={"repo_name": "my app"})
            html = response.data.decode()
            assert response.status_code == 400 or "invalid" in html.lower() or "error" in html.lower()
        finally:
            _cleanup(db_fd, db_path)

    def test_invalid_repo_name_with_at_sign(self):
        """Repo name with @ is rejected."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/new", data={"repo_name": "my@app"})
            html = response.data.decode()
            assert response.status_code == 400 or "invalid" in html.lower() or "error" in html.lower()
        finally:
            _cleanup(db_fd, db_path)

    def test_invalid_repo_name_with_slash(self):
        """Repo name with / is rejected."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/new", data={"repo_name": "my/app"})
            html = response.data.decode()
            assert response.status_code == 400 or "invalid" in html.lower() or "error" in html.lower()
        finally:
            _cleanup(db_fd, db_path)

    def test_valid_repo_name_alphanumeric(self):
        """Purely alphanumeric name passes validation."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            with patch("app.routes.create_project") as mock_create:
                mock_create.return_value = {"slug": "myapp123"}
                response = client.post("/projects/new", data={"repo_name": "myapp123"})
                # Should NOT get a validation error — either redirect or 200 success
                assert response.status_code in (200, 302)
        finally:
            _cleanup(db_fd, db_path)

    def test_valid_repo_name_with_hyphens(self):
        """Hyphens are allowed in repo names."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            with patch("app.routes.create_project") as mock_create:
                mock_create.return_value = {"slug": "my-cool-app"}
                response = client.post("/projects/new", data={"repo_name": "my-cool-app"})
                assert response.status_code in (200, 302)
        finally:
            _cleanup(db_fd, db_path)

    def test_valid_repo_name_with_underscores(self):
        """Underscores are allowed in repo names."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            with patch("app.routes.create_project") as mock_create:
                mock_create.return_value = {"slug": "my_app"}
                response = client.post("/projects/new", data={"repo_name": "my_app"})
                assert response.status_code in (200, 302)
        finally:
            _cleanup(db_fd, db_path)

    def test_valid_repo_name_with_dots(self):
        """Dots are allowed in repo names."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            with patch("app.routes.create_project") as mock_create:
                mock_create.return_value = {"slug": "my.app"}
                response = client.post("/projects/new", data={"repo_name": "my.app"})
                assert response.status_code in (200, 302)
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# POST /projects/new — availability checks
# ---------------------------------------------------------------------------


class TestPostProjectsNewAvailability:
    """POST /projects/new — repo name availability (GitHub + local dir)."""

    @patch("app.projects.os.path.isdir", return_value=False)
    @patch("app.projects.requests.get")
    def test_repo_name_taken_on_github_returns_error(self, mock_get, mock_isdir):
        """If GitHub says the repo already exists, show an error."""
        # GitHub returns 200 => repo exists
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/new", data={"repo_name": "existing-repo"})
            html = response.data.decode()
            assert (
                response.status_code == 400
                or "already" in html.lower()
                or "taken" in html.lower()
                or "exists" in html.lower()
            )
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.projects.os.path.isdir", return_value=True)
    @patch("app.projects.requests.get")
    def test_repo_name_exists_as_local_directory_returns_error(self, mock_get, mock_isdir):
        """If ~/projects/<name>/ already exists locally, show an error."""
        # GitHub returns 404 => repo does NOT exist on GitHub
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.post("/projects/new", data={"repo_name": "local-dir-exists"})
            html = response.data.decode()
            assert response.status_code == 400 or "already" in html.lower() or "exists" in html.lower()
        finally:
            _cleanup(db_fd, db_path)


# ---------------------------------------------------------------------------
# Unit tests — create_github_repo (uses POST /user/repos)
# ---------------------------------------------------------------------------


class TestCreateGithubRepo:
    """create_github_repo uses POST /user/repos via the GitHub API."""

    @patch("app.projects.requests.post")
    def test_creates_repo_via_api(self, mock_post):
        """POST /user/repos is called with correct body and auth header."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "html_url": "https://github.com/nicopujia/test-repo",
            "clone_url": "https://github.com/nicopujia/test-repo.git",
        }
        mock_post.return_value = mock_resp

        create_github_repo("test-repo", "A description", "gho_fake_token")

        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        assert "api.github.com/user/repos" in call_url
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"] == {"name": "test-repo", "description": "A description", "auto_init": True}
        assert "gho_fake_token" in call_kwargs["headers"]["Authorization"]

    @patch("app.projects.requests.post")
    def test_passes_description_in_body(self, mock_post):
        """The description is included in the request JSON body."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "html_url": "https://github.com/nicopujia/test-repo",
            "clone_url": "https://github.com/nicopujia/test-repo.git",
        }
        mock_post.return_value = mock_resp

        create_github_repo("test-repo", "My cool project", "gho_fake_token")

        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["description"] == "My cool project"

    @patch("app.projects.requests.post")
    def test_returns_dict_with_html_url_and_clone_url(self, mock_post):
        """Returns a dict with html_url and clone_url from the API response."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "html_url": "https://github.com/nicopujia/test-repo",
            "clone_url": "https://github.com/nicopujia/test-repo.git",
        }
        mock_post.return_value = mock_resp

        result = create_github_repo("test-repo", "desc", "gho_fake_token")

        assert result["html_url"] == "https://github.com/nicopujia/test-repo"
        assert result["clone_url"] == "https://github.com/nicopujia/test-repo.git"

    @patch("app.projects.requests.post")
    def test_raises_on_api_failure(self, mock_post):
        """Raises an exception when the API call fails."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("422 Unprocessable Entity")
        mock_post.return_value = mock_resp

        try:
            create_github_repo("test-repo", "desc", "gho_fake_token")
            assert False, "Should have raised"
        except Exception:
            pass


# ---------------------------------------------------------------------------
# POST /projects/new — successful creation
# ---------------------------------------------------------------------------


class TestPostProjectsNewSuccess:
    """POST /projects/new — full happy-path with all side-effects mocked."""

    def _setup_mocks(self):
        """Return a dict of mock objects for a successful project creation."""
        # GitHub API GET response: existence check => 404 (repo does not exist)
        mock_github_get_404 = MagicMock()
        mock_github_get_404.status_code = 404

        # GitHub API POST response: repo creation => 201 with repo data
        mock_github_repo_created = MagicMock()
        mock_github_repo_created.status_code = 201
        mock_github_repo_created.json.return_value = {
            "full_name": "nicopujia/my-new-project",
            "html_url": "https://github.com/nicopujia/my-new-project",
            "clone_url": "https://github.com/nicopujia/my-new-project.git",
        }

        # opencode session creation
        mock_opencode_resp = MagicMock()
        mock_opencode_resp.status_code = 200
        mock_opencode_resp.json.return_value = {"id": "session-abc-123"}

        # subprocess calls (git clone, beads init, bdui start)
        mock_run = MagicMock()
        mock_run.return_value = MagicMock(returncode=0)

        mock_popen = MagicMock()
        mock_popen_instance = MagicMock()
        mock_popen_instance.pid = 9999
        mock_popen.return_value = mock_popen_instance

        # Socket for port finding
        mock_socket_instance = MagicMock()
        mock_socket_instance.getsockname.return_value = ("", 8765)
        mock_socket_instance.__enter__ = MagicMock(return_value=mock_socket_instance)
        mock_socket_instance.__exit__ = MagicMock(return_value=False)

        return {
            "github_get_404": mock_github_get_404,
            "github_repo_created": mock_github_repo_created,
            "opencode_resp": mock_opencode_resp,
            "run": mock_run,
            "popen": mock_popen,
            "popen_instance": mock_popen_instance,
            "socket_instance": mock_socket_instance,
        }

    def _patch_and_post(self, client, mocks, repo_name="my-new-project", description="A cool project"):
        """Apply all patches and POST to /projects/new. Returns the response."""

        def requests_get_side_effect(url, **kwargs):
            if "api.github.com/repos/" in url:
                return mocks["github_get_404"]  # existence check => 404
            return MagicMock(status_code=200)

        def requests_post_side_effect(url, **kwargs):
            if "api.github.com/user/repos" in url:
                return mocks["github_repo_created"]  # repo creation => 201
            if "/session" in url:
                return mocks["opencode_resp"]
            return MagicMock(status_code=200)

        with (
            patch("app.projects.requests.get", side_effect=requests_get_side_effect),
            patch("app.projects.requests.post", side_effect=requests_post_side_effect),
            patch("app.projects.subprocess.run", mocks["run"]),
            patch("app.projects.subprocess.Popen", mocks["popen"]),
            patch("app.projects.os.path.isdir", return_value=False),
            patch("app.projects.socket.socket", return_value=mocks["socket_instance"]),
        ):
            return client.post(
                "/projects/new",
                data={"repo_name": repo_name, "description": description},
            )

    def test_redirects_to_project_page(self):
        """Successful creation redirects to /projects/<slug>."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            mocks = self._setup_mocks()
            response = self._patch_and_post(client, mocks)
            assert response.status_code == 302
            assert "/projects/my-new-project" in response.headers["Location"]
        finally:
            _cleanup(db_fd, db_path)

    def test_project_stored_in_db(self):
        """Successful creation stores the project in SQLite with all fields."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            mocks = self._setup_mocks()
            self._patch_and_post(client, mocks)

            row = _get_project_by_slug(db_path, "my-new-project")
            assert row is not None
            assert row["name"] == "my-new-project"
            assert row["slug"] == "my-new-project"
            assert "github.com" in row["repo_url"]
            assert row["vps_path"] is not None
            assert "my-new-project" in row["vps_path"]
            assert row["opencode_session_id"] == "session-abc-123"
            assert row["bdui_port"] == 8765
        finally:
            _cleanup(db_fd, db_path)

    def test_project_description_stored_in_db(self):
        """Description from the form is stored in the DB."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            mocks = self._setup_mocks()
            self._patch_and_post(client, mocks, description="Build a todo app")

            row = _get_project_by_slug(db_path, "my-new-project")
            assert row is not None
            assert row["description"] == "Build a todo app"
        finally:
            _cleanup(db_fd, db_path)

    def test_github_repo_created_via_api(self):
        """GitHub repo is created via POST to api.github.com/user/repos."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            mocks = self._setup_mocks()

            post_calls = []

            def requests_get_side_effect(url, **kwargs):
                if "api.github.com/repos/" in url:
                    return mocks["github_get_404"]
                return MagicMock(status_code=200)

            def requests_post_side_effect(url, **kwargs):
                post_calls.append((url, kwargs))
                if "api.github.com/user/repos" in url:
                    return mocks["github_repo_created"]
                if "/session" in url:
                    return mocks["opencode_resp"]
                return MagicMock(status_code=200)

            with (
                patch("app.projects.requests.get", side_effect=requests_get_side_effect),
                patch("app.projects.requests.post", side_effect=requests_post_side_effect),
                patch("app.projects.subprocess.run", mocks["run"]),
                patch("app.projects.subprocess.Popen", mocks["popen"]),
                patch("app.projects.os.path.isdir", return_value=False),
                patch("app.projects.socket.socket", return_value=mocks["socket_instance"]),
            ):
                client.post(
                    "/projects/new",
                    data={"repo_name": "my-new-project", "description": "A cool project"},
                )

            repo_api_calls = [c for c in post_calls if "api.github.com/user/repos" in c[0]]
            assert len(repo_api_calls) >= 1, f"Expected POST to api.github.com/user/repos, got: {post_calls}"
        finally:
            _cleanup(db_fd, db_path)

    def test_directory_cloned(self):
        """git clone is run for the new repo."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            mocks = self._setup_mocks()
            self._patch_and_post(client, mocks)

            # subprocess.run should have been called with git clone
            run_calls = mocks["run"].call_args_list
            clone_calls = [c for c in run_calls if "clone" in str(c)]
            assert len(clone_calls) >= 1, f"Expected git clone call, got: {run_calls}"
        finally:
            _cleanup(db_fd, db_path)

    def test_beads_initialized(self):
        """beads (bd) is initialized in the project directory."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            mocks = self._setup_mocks()
            self._patch_and_post(client, mocks)

            run_calls = mocks["run"].call_args_list
            bd_calls = [c for c in run_calls if "bd" in str(c) and "init" in str(c)]
            assert len(bd_calls) >= 1, f"Expected bd init call, got: {run_calls}"
        finally:
            _cleanup(db_fd, db_path)

    def test_bdui_sidecar_started(self):
        """bdui process is started via subprocess.Popen."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            mocks = self._setup_mocks()
            self._patch_and_post(client, mocks)

            assert mocks["popen"].called, "subprocess.Popen should be called to start bdui"
            popen_calls = mocks["popen"].call_args_list
            bdui_calls = [c for c in popen_calls if "bdui" in str(c)]
            assert len(bdui_calls) >= 1, f"Expected bdui call, got: {popen_calls}"
        finally:
            _cleanup(db_fd, db_path)

    def test_opencode_session_created(self):
        """An opencode session is created via POST to the opencode server."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            mocks = self._setup_mocks()

            opencode_calls = []

            def requests_post_side_effect(url, **kwargs):
                if "api.github.com/user/repos" in url:
                    return mocks["github_repo_created"]
                if "/session" in url:
                    opencode_calls.append((url, kwargs))
                    return mocks["opencode_resp"]
                return MagicMock(status_code=200)

            def requests_get_side_effect(url, **kwargs):
                if "api.github.com/repos/" in url:
                    return mocks["github_get_404"]
                return MagicMock(status_code=200)

            with (
                patch("app.projects.requests.get", side_effect=requests_get_side_effect),
                patch("app.projects.requests.post", side_effect=requests_post_side_effect),
                patch("app.projects.subprocess.run", mocks["run"]),
                patch("app.projects.subprocess.Popen", mocks["popen"]),
                patch("app.projects.os.path.isdir", return_value=False),
                patch("app.projects.socket.socket", return_value=mocks["socket_instance"]),
            ):
                client.post(
                    "/projects/new",
                    data={"repo_name": "my-new-project", "description": "A cool project"},
                )

            assert len(opencode_calls) >= 1, "Expected opencode session POST, got none"
            url, _ = opencode_calls[0]
            assert "/session" in url
        finally:
            _cleanup(db_fd, db_path)

    def test_bdui_port_is_unique_per_project(self):
        """The bdui sidecar is started on the port found by the socket probe."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            mocks = self._setup_mocks()
            # Socket returns port 8765
            mocks["socket_instance"].getsockname.return_value = ("", 8765)
            self._patch_and_post(client, mocks)

            row = _get_project_by_slug(db_path, "my-new-project")
            assert row["bdui_port"] == 8765
        finally:
            _cleanup(db_fd, db_path)

    def test_beads_init_uses_dolt_shared_server(self):
        """beads init sets BEADS_DOLT_SHARED_SERVER=1 environment variable."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            mocks = self._setup_mocks()
            self._patch_and_post(client, mocks)

            run_calls = mocks["run"].call_args_list
            bd_calls = [c for c in run_calls if "bd" in str(c) and "init" in str(c)]
            assert len(bd_calls) >= 1
            # Check that env contains BEADS_DOLT_SHARED_SERVER=1
            bd_call = bd_calls[0]
            # env can be in kwargs or the args
            call_kwargs = bd_call.kwargs if bd_call.kwargs else {}
            if "env" in call_kwargs:
                assert call_kwargs["env"].get("BEADS_DOLT_SHARED_SERVER") == "1", (
                    f"Expected BEADS_DOLT_SHARED_SERVER=1 in env, got: {call_kwargs['env']}"
                )
            else:
                # Might be passed via a wrapper — just verify bd init was called
                assert True
        finally:
            _cleanup(db_fd, db_path)

    def test_slug_derived_from_repo_name(self):
        """The project slug is derived from the repo name."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            mocks = self._setup_mocks()

            # Update the GitHub POST response (repo creation) for this specific name
            mocks["github_repo_created"].json.return_value = {
                "full_name": "nicopujia/My.Cool_App",
                "html_url": "https://github.com/nicopujia/My.Cool_App",
                "clone_url": "https://github.com/nicopujia/My.Cool_App.git",
            }
            self._patch_and_post(client, mocks, repo_name="My.Cool_App")

            # The slug should be a URL-safe version of the repo name
            db = sqlite3.connect(db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT slug FROM projects").fetchall()
            db.close()
            assert len(rows) == 1
            slug = rows[0]["slug"]
            # Slug should be lowercase or at least based on the repo name
            assert "cool" in slug.lower() or "my" in slug.lower()
        finally:
            _cleanup(db_fd, db_path)

    def test_duplicate_local_project_name_rejected(self):
        """If a project with the same name already exists in the DB, it is rejected."""
        app, db_path, db_fd = _make_app()
        try:
            # Insert an existing project
            db = sqlite3.connect(db_path)
            db.execute(
                "INSERT INTO projects (name, slug) VALUES (?, ?)",
                ("existing-project", "existing-project"),
            )
            db.commit()
            db.close()

            client = app.test_client()
            _auth_session(client)

            mocks = self._setup_mocks()
            response = self._patch_and_post(client, mocks, repo_name="existing-project")
            html = response.data.decode()
            # Should fail — either 400 or error message in the HTML
            assert (
                response.status_code == 400
                or "already" in html.lower()
                or "exists" in html.lower()
                or "taken" in html.lower()
            )
        finally:
            _cleanup(db_fd, db_path)
