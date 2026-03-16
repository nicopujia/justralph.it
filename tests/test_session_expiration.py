"""Tests for 30-day session inactivity auto-logout feature."""

import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

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


# --- Tests ---


class TestSessionExpiration:
    """Tests for 30-day session inactivity auto-logout."""

    def test_session_expires_after_30_days_of_inactivity(self):
        """A session older than 30 days is cleared and user is redirected to '/'."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            # Simulate a user logged in 31 days ago
            with client.session_transaction() as sess:
                sess["user"] = "nicopujia"
                sess["github_token"] = "gho_test_token"
                sess["last_activity"] = (datetime.utcnow() - timedelta(days=31)).isoformat()

            # Mock datetime.utcnow to return current time
            with patch("app.datetime") as mock_datetime:
                mock_datetime.utcnow.return_value = datetime.utcnow()
                mock_datetime.fromisoformat = datetime.fromisoformat
                mock_datetime.timedelta = timedelta
                response = client.get("/projects")

            # Should be redirected to root due to session expiration
            assert response.status_code == 302
            assert response.headers["Location"] == "/"

            # Session should be cleared
            with client.session_transaction() as sess:
                assert "user" not in sess
                assert "github_token" not in sess
        finally:
            _cleanup(db_fd, db_path)

    def test_session_active_within_30_days(self):
        """A session that was active 29 days ago is still valid."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            # Simulate a user logged in 29 days ago
            with client.session_transaction() as sess:
                sess["user"] = "nicopujia"
                sess["github_token"] = "gho_test_token"
                sess["last_activity"] = (datetime.utcnow() - timedelta(days=29)).isoformat()

            # Mock datetime.utcnow to return current time
            with patch("app.datetime") as mock_datetime:
                mock_datetime.utcnow.return_value = datetime.utcnow()
                mock_datetime.fromisoformat = datetime.fromisoformat
                mock_datetime.timedelta = timedelta
                response = client.get("/projects")

            # Should not be redirected (projects page returns 200)
            assert response.status_code == 200

            # Session should still contain user data
            with client.session_transaction() as sess:
                assert sess["user"] == "nicopujia"
                assert sess["github_token"] == "gho_test_token"
        finally:
            _cleanup(db_fd, db_path)

    def test_session_activity_timestamp_updated_on_request(self):
        """Verify that last_activity is updated to current time on each request."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            old_time = datetime.utcnow() - timedelta(days=5)
            new_time = datetime.utcnow()

            with client.session_transaction() as sess:
                sess["user"] = "nicopujia"
                sess["github_token"] = "gho_test_token"
                sess["last_activity"] = old_time.isoformat()

            # Mock datetime.utcnow to return a specific new time
            with patch("app.datetime") as mock_datetime:
                mock_datetime.utcnow.return_value = new_time
                mock_datetime.fromisoformat = datetime.fromisoformat
                mock_datetime.timedelta = timedelta
                client.get("/projects")

            # Check that last_activity was updated to the new time
            with client.session_transaction() as sess:
                updated_activity = datetime.fromisoformat(sess["last_activity"])
                assert updated_activity == new_time
        finally:
            _cleanup(db_fd, db_path)

    def test_session_last_activity_set_on_first_login(self):
        """Verify that last_activity is set when user first logs in."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            current_time = datetime.utcnow()

            # User has no last_activity yet
            with client.session_transaction() as sess:
                sess["user"] = "nicopujia"
                sess["github_token"] = "gho_test_token"
                # No last_activity set

            # Mock datetime.utcnow to return a specific time
            with patch("app.datetime") as mock_datetime:
                mock_datetime.utcnow.return_value = current_time
                mock_datetime.fromisoformat = datetime.fromisoformat
                mock_datetime.timedelta = timedelta
                client.get("/projects")

            # Check that last_activity was set to current time
            with client.session_transaction() as sess:
                assert "last_activity" in sess
                last_activity = datetime.fromisoformat(sess["last_activity"])
                assert last_activity == current_time
        finally:
            _cleanup(db_fd, db_path)
