"""Tests for GitHub App authentication flow."""

import os
import tempfile
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app import create_app

# --- Test fixtures ---

# Generate a temporary RSA key pair for testing
_test_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_test_private_key_pem = _test_private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
)
_test_public_key = _test_private_key.public_key()


def _make_app(pem_path):
    """Create a test app with a temp DB and the given PEM path."""
    db_fd, db_path = tempfile.mkstemp()
    app = create_app(
        {
            "DATABASE": db_path,
            "TESTING": True,
            "GITHUB_APP_ID": 12345,
            "GITHUB_APP_SLUG": "just-ralph-it",
            "GITHUB_PRIVATE_KEY_PATH": pem_path,
        }
    )
    return app, db_path, db_fd


def _cleanup(db_fd, db_path):
    os.close(db_fd)
    os.unlink(db_path)


def _write_test_pem():
    """Write the test PEM key to a temp file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".pem")
    os.write(fd, _test_private_key_pem)
    os.close(fd)
    return path


# Mock GitHub API responses
def _mock_installation_response(login="nicopujia"):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "id": 99999,
        "account": {"login": login, "id": 1234},
        "app_id": 12345,
    }
    return resp


def _mock_access_token_response():
    resp = MagicMock()
    resp.status_code = 201
    resp.json.return_value = {
        "token": "ghs_test_token_abc123",
        "expires_at": "2026-03-15T12:00:00Z",
    }
    return resp


# --- Tests ---


class TestAuthGitHubRedirect:
    """Tests for GET /auth/github."""

    def test_auth_github_redirects_to_github_app_install(self):
        """GET /auth/github returns 302 to github.com/apps/just-ralph-it/installations/new."""
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                client = app.test_client()
                response = client.get("/auth/github")
                assert response.status_code == 302
                location = response.headers["Location"]
                parsed = urlparse(location)
                assert parsed.scheme == "https"
                assert parsed.netloc == "github.com"
                assert parsed.path == "/apps/just-ralph-it/installations/new"
                # Should have state param
                qs = parse_qs(parsed.query)
                assert "state" in qs
                assert len(qs["state"][0]) > 0
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)

    def test_auth_github_stores_state_in_session(self):
        """GET /auth/github stores the OAuth state in the session."""
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                client = app.test_client()
                response = client.get("/auth/github")
                # Extract state from redirect URL
                location = response.headers["Location"]
                qs = parse_qs(urlparse(location).query)
                redirect_state = qs["state"][0]

                with client.session_transaction() as sess:
                    assert sess.get("oauth_state") == redirect_state
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)


class TestAuthCallback:
    """Tests for GET /auth/callback."""

    def test_auth_callback_rejects_missing_installation_id_and_code(self):
        """GET /auth/callback without installation_id or code returns 400."""
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                client = app.test_client()
                with client.session_transaction() as sess:
                    sess["oauth_state"] = "test-state"
                response = client.get("/auth/callback?state=test-state")
                assert response.status_code == 400
                assert b"Missing installation_id or code" in response.data
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)

    def test_auth_callback_rejects_invalid_state(self):
        """GET /auth/callback with wrong state returns 400."""
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                client = app.test_client()
                with client.session_transaction() as sess:
                    sess["oauth_state"] = "correct-state"
                response = client.get("/auth/callback?installation_id=12345&state=wrong-state")
                assert response.status_code == 400
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)

    @patch("app.auth.github.get_installation")
    def test_auth_callback_rejects_non_nicopujia_user(self, mock_get_installation):
        """Non-nicopujia user sees 'Not available yet.' message."""
        mock_get_installation.return_value = {
            "id": 99999,
            "account": {"login": "someoneelse", "id": 5678},
        }
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                client = app.test_client()
                with client.session_transaction() as sess:
                    sess["oauth_state"] = "test-state"
                response = client.get("/auth/callback?installation_id=12345&state=test-state")
                assert response.status_code == 200
                assert b"Not available yet." in response.data
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)

    @patch("app.auth.github.create_installation_token")
    @patch("app.auth.github.get_installation")
    def test_auth_callback_accepts_nicopujia(self, mock_get_installation, mock_create_token):
        """nicopujia user is redirected to /projects after successful auth."""
        mock_get_installation.return_value = {
            "id": 99999,
            "account": {"login": "nicopujia", "id": 1234},
        }
        mock_create_token.return_value = {
            "token": "ghs_test_token",
            "expires_at": "2026-03-15T12:00:00Z",
        }
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                client = app.test_client()
                with client.session_transaction() as sess:
                    sess["oauth_state"] = "test-state"
                response = client.get("/auth/callback?installation_id=12345&state=test-state")
                assert response.status_code == 302
                assert "/projects" in response.headers["Location"]
                with client.session_transaction() as sess:
                    assert sess["user"] == "nicopujia"
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)

    @patch("app.auth.github.create_installation_token")
    @patch("app.auth.github.get_installation")
    def test_auth_callback_stores_installation_token_in_session(self, mock_get_installation, mock_create_token):
        """Session contains installation_id, installation_token, and token_expires_at after auth."""
        mock_get_installation.return_value = {
            "id": 99999,
            "account": {"login": "nicopujia", "id": 1234},
        }
        mock_create_token.return_value = {
            "token": "ghs_test_token_xyz",
            "expires_at": "2026-03-15T14:00:00Z",
        }
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                client = app.test_client()
                with client.session_transaction() as sess:
                    sess["oauth_state"] = "test-state"
                client.get("/auth/callback?installation_id=12345&state=test-state")
                with client.session_transaction() as sess:
                    assert sess["installation_id"] == "12345"
                    assert sess["installation_token"] == "ghs_test_token_xyz"
                    assert sess["token_expires_at"] == "2026-03-15T14:00:00Z"
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)

    @patch("app.auth.github.create_installation_token")
    @patch("app.auth.github.get_installation")
    def test_auth_callback_redirect_to_projects_returns_200(self, mock_get_installation, mock_create_token):
        """After auth callback, following the redirect to /projects returns 200 (not 404)."""
        mock_get_installation.return_value = {
            "id": 99999,
            "account": {"login": "nicopujia", "id": 1234},
        }
        mock_create_token.return_value = {
            "token": "ghs_test_token",
            "expires_at": "2026-03-15T12:00:00Z",
        }
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                client = app.test_client()
                with client.session_transaction() as sess:
                    sess["oauth_state"] = "test-state"
                # Step 1: Hit the auth callback (gets 302 to /projects)
                response = client.get("/auth/callback?installation_id=12345&state=test-state")
                assert response.status_code == 302
                assert "/projects" in response.headers["Location"]
                # Step 2: Follow the redirect — should get 200, not 404
                response = client.get("/projects")
                assert response.status_code == 200
                html = response.data.decode()
                assert "New Project" in html
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)

    @patch("app.auth.github.create_installation_token")
    @patch("app.auth.github.list_installations")
    def test_auth_callback_reauth_with_code_only(self, mock_list_installations, mock_create_token):
        """Re-auth with code (no installation_id) finds installation and succeeds."""
        mock_list_installations.return_value = [
            {"id": 99999, "account": {"login": "nicopujia", "id": 1234}, "app_id": 12345}
        ]
        mock_create_token.return_value = {
            "token": "ghs_reauth_token",
            "expires_at": "2026-03-15T14:00:00Z",
        }
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                client = app.test_client()
                with client.session_transaction() as sess:
                    sess["oauth_state"] = "test-state"
                response = client.get("/auth/callback?code=test-oauth-code&state=test-state")
                assert response.status_code == 302
                assert "/projects" in response.headers["Location"]
                with client.session_transaction() as sess:
                    assert sess["user"] == "nicopujia"
                    assert sess["installation_id"] == "99999"
                    assert sess["installation_token"] == "ghs_reauth_token"
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)

    @patch("app.auth.github.list_installations")
    def test_auth_callback_reauth_no_installations(self, mock_list_installations):
        """Re-auth with code but no installations returns 400."""
        mock_list_installations.return_value = []
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                client = app.test_client()
                with client.session_transaction() as sess:
                    sess["oauth_state"] = "test-state"
                response = client.get("/auth/callback?code=test-oauth-code&state=test-state")
                assert response.status_code == 400
                assert b"No installations found" in response.data
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)

    @patch("app.auth.github.list_installations")
    def test_auth_callback_reauth_non_nicopujia(self, mock_list_installations):
        """Re-auth where installation belongs to non-nicopujia user."""
        mock_list_installations.return_value = [
            {"id": 99999, "account": {"login": "someoneelse", "id": 5678}, "app_id": 12345}
        ]
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                client = app.test_client()
                with client.session_transaction() as sess:
                    sess["oauth_state"] = "test-state"
                response = client.get("/auth/callback?code=test-oauth-code&state=test-state")
                assert response.status_code == 200
                assert b"Not available yet." in response.data
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)

    @patch("app.auth.github.create_installation_token")
    @patch("app.auth.github.get_installation")
    def test_auth_callback_with_both_code_and_installation_id(self, mock_get_installation, mock_create_token):
        """Callback with both code and installation_id uses installation_id flow."""
        mock_get_installation.return_value = {"id": 99999, "account": {"login": "nicopujia", "id": 1234}}
        mock_create_token.return_value = {
            "token": "ghs_test_token",
            "expires_at": "2026-03-15T12:00:00Z",
        }
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                client = app.test_client()
                with client.session_transaction() as sess:
                    sess["oauth_state"] = "test-state"
                response = client.get("/auth/callback?installation_id=12345&code=test-code&state=test-state")
                assert response.status_code == 302
                mock_get_installation.assert_called_once_with("12345")
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)


class TestAuthLogout:
    """Tests for GET /auth/logout."""

    def test_auth_logout_clears_session(self):
        """GET /auth/logout clears session and redirects to /."""
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                client = app.test_client()
                with client.session_transaction() as sess:
                    sess["user"] = "nicopujia"
                    sess["installation_id"] = "12345"
                    sess["installation_token"] = "ghs_token"
                response = client.get("/auth/logout")
                assert response.status_code == 302
                assert response.headers["Location"] == "/"
                with client.session_transaction() as sess:
                    assert "user" not in sess
                    assert "installation_id" not in sess
                    assert "installation_token" not in sess
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)

    def test_authenticated_page_shows_logout_link(self):
        """Authenticated pages (e.g. /projects) contain a logout link."""
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                client = app.test_client()
                with client.session_transaction() as sess:
                    sess["user"] = "nicopujia"
                    sess["installation_id"] = "12345"
                response = client.get("/projects")
                html = response.data.decode()
                assert "/auth/logout" in html
                assert "Logout" in html
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)

    def test_unauthenticated_landing_page_no_logout_link(self):
        """The landing page when not authenticated does NOT show a logout link."""
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                client = app.test_client()
                response = client.get("/")
                html = response.data.decode()
                assert "/auth/logout" not in html
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)


class TestGenerateJWT:
    """Tests for the generate_jwt helper."""

    def test_generate_jwt_returns_valid_token(self):
        """generate_jwt() returns a valid RS256 JWT with correct claims."""
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                with app.app_context():
                    from app.github import generate_jwt

                    token = generate_jwt()

                    # Decode and verify
                    decoded = jwt.decode(
                        token,
                        _test_public_key,
                        algorithms=["RS256"],
                        options={"verify_exp": True},
                    )
                    assert decoded["iss"] == "12345"  # APP_ID as string
                    assert "iat" in decoded
                    assert "exp" in decoded
                    # exp should be ~10 minutes from now
                    assert decoded["exp"] - decoded["iat"] <= 660
                    assert decoded["exp"] - decoded["iat"] >= 600
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)


class TestListInstallations:
    """Tests for the list_installations helper."""

    @patch("app.github.requests.get")
    def test_list_installations_returns_list(self, mock_get):
        """list_installations() returns a list of installation dicts."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"id": 99999, "account": {"login": "nicopujia"}}]
        mock_get.return_value = mock_resp
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                with app.app_context():
                    from app.github import list_installations

                    result = list_installations()
                    assert result == [{"id": 99999, "account": {"login": "nicopujia"}}]
                    mock_get.assert_called_once()
                    call_args = mock_get.call_args
                    assert "/app/installations" in call_args[0][0]
                    assert "Bearer" in call_args[1]["headers"]["Authorization"]
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)

    @patch("app.github.requests.get")
    def test_list_installations_returns_empty_list(self, mock_get):
        """list_installations() returns empty list when no installations exist."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_get.return_value = mock_resp
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                with app.app_context():
                    from app.github import list_installations

                    result = list_installations()
                    assert result == []
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)


class TestIndexSignInLink:
    """Tests for the index page sign-in link."""

    def test_index_shows_sign_in_link(self):
        """Index page has a link to /auth/github."""
        pem_path = _write_test_pem()
        try:
            app, db_path, db_fd = _make_app(pem_path)
            try:
                client = app.test_client()
                response = client.get("/")
                assert b"/auth/github" in response.data
                assert b"Sign in with GitHub" in response.data
            finally:
                _cleanup(db_fd, db_path)
        finally:
            os.unlink(pem_path)
