"""Tests for GitHub OAuth authentication flow."""

import os
import tempfile
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from app import create_app

# --- Test fixtures ---


def _make_app():
    """Create a test app with a temp DB and OAuth config."""
    db_fd, db_path = tempfile.mkstemp()
    app = create_app(
        {
            "DATABASE": db_path,
            "TESTING": True,
            "GITHUB_CLIENT_ID": "test-client-id",
            "GITHUB_CLIENT_SECRET": "test-client-secret",
        }
    )
    return app, db_path, db_fd


def _cleanup(db_fd, db_path):
    os.close(db_fd)
    os.unlink(db_path)


def _mock_token_response():
    """Mock response from POST https://github.com/login/oauth/access_token."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "access_token": "gho_test_token",
        "token_type": "bearer",
        "scope": "repo,read:user",
    }
    return resp


def _mock_user_response(login="nicopujia", user_id=1234):
    """Mock response from GET https://api.github.com/user."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"login": login, "id": user_id}
    return resp


# --- Tests ---


class TestAuthGitHubRedirect:
    """Tests for GET /auth/github."""

    def test_auth_github_redirects_to_github_oauth_authorize(self):
        """GET /auth/github returns 302 to github.com/login/oauth/authorize with correct params."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.get("/auth/github")
            assert response.status_code == 302
            location = response.headers["Location"]
            parsed = urlparse(location)
            assert parsed.scheme == "https"
            assert parsed.netloc == "github.com"
            assert parsed.path == "/login/oauth/authorize"
            qs = parse_qs(parsed.query)
            assert qs["client_id"] == ["test-client-id"]
            assert "repo" in qs["scope"][0]
            assert "read:user" in qs["scope"][0]
            assert "state" in qs
            assert len(qs["state"][0]) > 0
            assert qs["redirect_uri"] == ["https://justralph.it/auth/callback"]
        finally:
            _cleanup(db_fd, db_path)

    def test_auth_github_scope_contains_repo_and_read_user(self):
        """GET /auth/github redirect URL includes both 'repo' and 'read:user' scopes."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.get("/auth/github")
            location = response.headers["Location"]
            qs = parse_qs(urlparse(location).query)
            scope_value = qs["scope"][0]
            # Scopes may be space-delimited, comma-delimited, or URL-encoded.
            # Just verify both required scopes appear in the raw value.
            assert "repo" in scope_value
            assert "read:user" in scope_value or "read%3Auser" in scope_value
        finally:
            _cleanup(db_fd, db_path)

    def test_auth_github_stores_state_in_session(self):
        """GET /auth/github stores the OAuth state in the session."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.get("/auth/github")
            location = response.headers["Location"]
            qs = parse_qs(urlparse(location).query)
            redirect_state = qs["state"][0]

            with client.session_transaction() as sess:
                assert sess.get("oauth_state") == redirect_state
        finally:
            _cleanup(db_fd, db_path)


class TestAuthCallback:
    """Tests for GET /auth/callback."""

    def test_auth_callback_rejects_missing_code(self):
        """GET /auth/callback without code returns 400."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["oauth_state"] = "test-state"
            response = client.get("/auth/callback?state=test-state")
            assert response.status_code == 400
        finally:
            _cleanup(db_fd, db_path)

    def test_auth_callback_rejects_invalid_state(self):
        """GET /auth/callback with wrong state returns 400."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["oauth_state"] = "correct-state"
            response = client.get("/auth/callback?code=test-code&state=wrong-state")
            assert response.status_code == 400
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.auth.requests.get")
    @patch("app.auth.requests.post")
    def test_auth_callback_exchanges_code_for_token(self, mock_post, mock_get):
        """Callback exchanges code for token via POST to github.com/login/oauth/access_token."""
        mock_post.return_value = _mock_token_response()
        mock_get.return_value = _mock_user_response()
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["oauth_state"] = "test-state"
            client.get("/auth/callback?code=test-code&state=test-state")
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "https://github.com/login/oauth/access_token" in call_args[0][0]
            posted_json = (
                call_args[1].get("json")
                or call_args[1].get("data")
                or (call_args[1] if "client_id" in call_args[1] else call_args[0][1] if len(call_args[0]) > 1 else {})
            )
            # Check that client_id, client_secret, and code were sent
            # The implementation might use json= or data= — check the actual call
            if "json" in call_args[1]:
                payload = call_args[1]["json"]
            elif "data" in call_args[1]:
                payload = call_args[1]["data"]
            else:
                payload = {}
            assert payload.get("client_id") == "test-client-id"
            assert payload.get("client_secret") == "test-client-secret"
            assert payload.get("code") == "test-code"
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.auth.requests.get")
    @patch("app.auth.requests.post")
    def test_auth_callback_rejects_non_nicopujia_user(self, mock_post, mock_get):
        """Non-nicopujia user sees 'Not available yet.' message."""
        mock_post.return_value = _mock_token_response()
        mock_get.return_value = _mock_user_response(login="someoneelse", user_id=5678)
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["oauth_state"] = "test-state"
            response = client.get("/auth/callback?code=test-code&state=test-state")
            assert response.status_code == 200
            assert b"Not available yet." in response.data
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.auth.requests.get")
    @patch("app.auth.requests.post")
    def test_auth_callback_accepts_nicopujia(self, mock_post, mock_get):
        """nicopujia user is redirected to /projects after successful auth."""
        mock_post.return_value = _mock_token_response()
        mock_get.return_value = _mock_user_response()
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["oauth_state"] = "test-state"
            response = client.get("/auth/callback?code=test-code&state=test-state")
            assert response.status_code == 302
            assert "/projects" in response.headers["Location"]
            with client.session_transaction() as sess:
                assert sess["user"] == "nicopujia"
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.auth.requests.get")
    @patch("app.auth.requests.post")
    def test_auth_callback_stores_github_token_in_session(self, mock_post, mock_get):
        """Session contains github_token (not installation_token) after auth."""
        mock_post.return_value = _mock_token_response()
        mock_get.return_value = _mock_user_response()
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["oauth_state"] = "test-state"
            client.get("/auth/callback?code=test-code&state=test-state")
            with client.session_transaction() as sess:
                assert sess["github_token"] == "gho_test_token"
                assert "installation_token" not in sess
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.auth.requests.get")
    @patch("app.auth.requests.post")
    def test_auth_callback_cleans_up_oauth_state(self, mock_post, mock_get):
        """oauth_state is removed from session after successful auth."""
        mock_post.return_value = _mock_token_response()
        mock_get.return_value = _mock_user_response()
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["oauth_state"] = "test-state"
            client.get("/auth/callback?code=test-code&state=test-state")
            with client.session_transaction() as sess:
                assert "oauth_state" not in sess
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.auth.requests.get")
    @patch("app.auth.requests.post")
    def test_auth_callback_re_signin_works(self, mock_post, mock_get):
        """Re-signing in (going through the flow again) works correctly."""
        mock_post.return_value = _mock_token_response()
        mock_get.return_value = _mock_user_response()
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            # First sign-in
            with client.session_transaction() as sess:
                sess["oauth_state"] = "state-1"
            response = client.get("/auth/callback?code=code-1&state=state-1")
            assert response.status_code == 302
            with client.session_transaction() as sess:
                assert sess["user"] == "nicopujia"
                assert sess["github_token"] == "gho_test_token"

            # Second sign-in (re-auth)
            second_token_resp = MagicMock()
            second_token_resp.status_code = 200
            second_token_resp.json.return_value = {
                "access_token": "gho_second_token",
                "token_type": "bearer",
                "scope": "repo,read:user",
            }
            mock_post.return_value = second_token_resp

            with client.session_transaction() as sess:
                sess["oauth_state"] = "state-2"
            response = client.get("/auth/callback?code=code-2&state=state-2")
            assert response.status_code == 302
            with client.session_transaction() as sess:
                assert sess["user"] == "nicopujia"
                assert sess["github_token"] == "gho_second_token"
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.auth.requests.get")
    @patch("app.auth.requests.post")
    def test_auth_callback_redirect_to_projects_returns_200(self, mock_post, mock_get):
        """After auth callback, following the redirect to /projects returns 200."""
        mock_post.return_value = _mock_token_response()
        mock_get.return_value = _mock_user_response()
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["oauth_state"] = "test-state"
            response = client.get("/auth/callback?code=test-code&state=test-state")
            assert response.status_code == 302
            assert "/projects" in response.headers["Location"]
            # Follow the redirect
            response = client.get("/projects")
            assert response.status_code == 200
            html = response.data.decode()
            assert "New Project" in html
        finally:
            _cleanup(db_fd, db_path)


class TestAuthLogout:
    """Tests for GET /auth/logout."""

    def test_auth_logout_clears_session(self):
        """GET /auth/logout clears user and github_token from session and redirects to /."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["user"] = "nicopujia"
                sess["github_token"] = "gho_test_token"
            response = client.get("/auth/logout")
            assert response.status_code == 302
            assert response.headers["Location"] == "/"
            with client.session_transaction() as sess:
                assert "user" not in sess
                assert "github_token" not in sess
        finally:
            _cleanup(db_fd, db_path)

    def test_authenticated_page_shows_logout_link(self):
        """Authenticated pages (e.g. /projects) contain a logout link."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["user"] = "nicopujia"
                sess["github_token"] = "gho_test_token"
            response = client.get("/projects")
            html = response.data.decode()
            assert "/auth/logout" in html
            assert "Logout" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_unauthenticated_landing_page_no_logout_link(self):
        """The landing page when not authenticated does NOT show a logout link."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.get("/")
            html = response.data.decode()
            assert "/auth/logout" not in html
        finally:
            _cleanup(db_fd, db_path)


class TestIndexSignInLink:
    """Tests for the index page sign-in link."""

    def test_index_shows_sign_in_link(self):
        """Index page has a link to /auth/github."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.get("/")
            assert b"/auth/github" in response.data
            assert b"Sign in with GitHub" in response.data
        finally:
            _cleanup(db_fd, db_path)


class TestLoadDotenvOverride:
    """Verify that .env values override pre-existing OS environment variables."""

    def test_dotenv_overrides_stale_env_var(self):
        """load_dotenv(override=True) ensures .env wins over pre-set env vars.

        Simulates the systemd EnvironmentFile scenario: a stale GITHUB_CLIENT_ID
        is already in os.environ before load_dotenv runs. After importing the app
        module (which calls load_dotenv at import time), the .env value must win.
        """
        import importlib

        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")

        # Read the real GITHUB_CLIENT_ID from .env
        real_client_id = None
        with open(env_path) as f:
            for line in f:
                if line.startswith("GITHUB_CLIENT_ID="):
                    real_client_id = line.strip().split("=", 1)[1]
                    break
        assert real_client_id is not None, ".env must contain GITHUB_CLIENT_ID"

        stale_id = "Iv23liLbwSkcZh1rfD2Z"
        assert stale_id != real_client_id, "stale ID must differ from real .env value"

        # Set a stale value (simulating systemd EnvironmentFile)
        original = os.environ.get("GITHUB_CLIENT_ID")
        os.environ["GITHUB_CLIENT_ID"] = stale_id
        import app as app_module

        try:
            # Re-import app module to re-run load_dotenv at module scope
            importlib.reload(app_module)

            # After reload, os.environ should have the .env value, not the stale one
            assert os.environ["GITHUB_CLIENT_ID"] == real_client_id, (
                f"Expected .env value '{real_client_id}' but got '{os.environ['GITHUB_CLIENT_ID']}'. "
                "load_dotenv must be called with override=True."
            )
        finally:
            # Restore original env
            if original is None:
                os.environ.pop("GITHUB_CLIENT_ID", None)
            else:
                os.environ["GITHUB_CLIENT_ID"] = original
            # Reload again to restore clean state
            importlib.reload(app_module)
