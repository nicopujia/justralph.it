"""Tests for browser push notifications for Ralph loop events (TDD).

Feature: When the user clicks "Just Ralph It," the browser requests push
notification permission. If granted, the subscription is stored server-side.
When ralph.py exits with HUMAN_NEEDED or ALL_DONE, the server sends a push
notification to all stored subscriptions for that project.

Backend endpoints:
- POST   /projects/<slug>/push/subscribe   — store a push subscription
- DELETE /projects/<slug>/push/subscribe   — remove a push subscription
- GET    /projects/<slug>/push/vapid-key   — return the VAPID public key

Database:
- push_subscriptions table with id, project_slug, subscription_json, created_at

Integration with _watch_ralph:
- Calls send_push_notification on ralph stop (all_done / human_needed)

Frontend:
- <link rel="manifest">, service worker registration, VAPID_PUBLIC_KEY JS var
- /static/sw.js served
"""

import json
import os
import sqlite3
import tempfile
import time
from unittest.mock import MagicMock, patch

from app import create_app

# ---------------------------------------------------------------------------
# Helpers (same pattern as other test files)
# ---------------------------------------------------------------------------

SAMPLE_SUBSCRIPTION = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/test-endpoint-123",
    "keys": {
        "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUlnlh0T0fTlFXwxDnHdU1gBcWOR6qJpMEpMXeY=",
        "auth": "tBHItJI5svbpC7HmL-Ql_A==",
    },
}

TEST_VAPID_KEY = "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkDs--2eu7POd6x3E-4ICtBRoTNIo-AX0eouStFm4="


def _make_app():
    """Create app with a temp DB and return (app, db_path, db_fd)."""
    db_fd, db_path = tempfile.mkstemp()
    app = create_app(
        {
            "DATABASE": db_path,
            "TESTING": True,
            "VAPID_APPLICATION_SERVER_KEY": TEST_VAPID_KEY,
        }
    )
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


def _insert_project(
    db_path,
    name="test-project",
    slug="test-project",
    ralph_running=0,
    vps_path="/home/nico/projects/test-project",
):
    """Insert a project directly into the DB."""
    db = sqlite3.connect(db_path)
    db.execute(
        """INSERT INTO projects (name, slug, ralph_running, vps_path)
           VALUES (?, ?, ?, ?)""",
        (name, slug, ralph_running, vps_path),
    )
    db.commit()
    db.close()


def _insert_subscription(db_path, slug="test-project", subscription=None):
    """Insert a push subscription directly into the DB."""
    if subscription is None:
        subscription = SAMPLE_SUBSCRIPTION
    db = sqlite3.connect(db_path)
    db.execute(
        "INSERT INTO push_subscriptions (project_slug, subscription_json) VALUES (?, ?)",
        (slug, json.dumps(subscription)),
    )
    db.commit()
    db.close()


# ===========================================================================
# Database: push_subscriptions table
# ===========================================================================


class TestPushSubscriptionsTable:
    """The push_subscriptions table is created during app init."""

    def test_table_exists(self):
        """push_subscriptions table exists after app creation."""
        app, db_path, db_fd = _make_app()
        try:
            db = sqlite3.connect(db_path)
            cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='push_subscriptions'")
            assert cursor.fetchone() is not None
            db.close()
        finally:
            _cleanup(db_fd, db_path)

    def test_table_has_expected_columns(self):
        """push_subscriptions table has id, project_slug, subscription_json, created_at."""
        app, db_path, db_fd = _make_app()
        try:
            db = sqlite3.connect(db_path)
            cursor = db.execute("PRAGMA table_info(push_subscriptions)")
            columns = {row[1] for row in cursor.fetchall()}
            db.close()
            assert "id" in columns
            assert "project_slug" in columns
            assert "subscription_json" in columns
            assert "created_at" in columns
        finally:
            _cleanup(db_fd, db_path)

    def test_subscriptions_can_be_stored_and_retrieved(self):
        """Subscriptions can be inserted and queried back."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_subscription(db_path, slug="my-project")
            db = sqlite3.connect(db_path)
            rows = db.execute(
                "SELECT project_slug, subscription_json FROM push_subscriptions WHERE project_slug = ?",
                ("my-project",),
            ).fetchall()
            db.close()
            assert len(rows) == 1
            assert rows[0][0] == "my-project"
            stored = json.loads(rows[0][1])
            assert stored["endpoint"] == SAMPLE_SUBSCRIPTION["endpoint"]
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# POST /projects/<slug>/push/subscribe
# ===========================================================================


class TestPushSubscribeAuth:
    """Auth gating for POST /projects/<slug>/push/subscribe."""

    def test_unauthenticated_redirects(self):
        """Unauthenticated request redirects to /."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.post(
                "/projects/test-project/push/subscribe",
                json={"subscription": SAMPLE_SUBSCRIPTION},
            )
            assert response.status_code == 302
            assert response.headers["Location"] == "/"
        finally:
            _cleanup(db_fd, db_path)

    def test_nonexistent_project_returns_404(self):
        """Authenticated request for nonexistent project returns 404."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.post(
                "/projects/nonexistent/push/subscribe",
                json={"subscription": SAMPLE_SUBSCRIPTION},
            )
            assert response.status_code == 404
        finally:
            _cleanup(db_fd, db_path)


class TestPushSubscribeSuccess:
    """POST /projects/<slug>/push/subscribe stores the subscription."""

    def test_returns_204_on_success(self):
        """Returns 204 No Content on successful subscription."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.post(
                "/projects/test-project/push/subscribe",
                json={"subscription": SAMPLE_SUBSCRIPTION},
            )
            assert response.status_code == 204
        finally:
            _cleanup(db_fd, db_path)

    def test_stores_subscription_in_db(self):
        """The subscription JSON is stored in push_subscriptions table."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            client.post(
                "/projects/test-project/push/subscribe",
                json={"subscription": SAMPLE_SUBSCRIPTION},
            )
            db = sqlite3.connect(db_path)
            rows = db.execute(
                "SELECT subscription_json FROM push_subscriptions WHERE project_slug = ?",
                ("test-project",),
            ).fetchall()
            db.close()
            assert len(rows) == 1
            stored = json.loads(rows[0][0])
            assert stored["endpoint"] == SAMPLE_SUBSCRIPTION["endpoint"]
            assert stored["keys"]["p256dh"] == SAMPLE_SUBSCRIPTION["keys"]["p256dh"]
            assert stored["keys"]["auth"] == SAMPLE_SUBSCRIPTION["keys"]["auth"]
        finally:
            _cleanup(db_fd, db_path)

    def test_stores_multiple_subscriptions(self):
        """Multiple subscriptions can be stored for the same project."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)

            sub1 = {**SAMPLE_SUBSCRIPTION, "endpoint": "https://example.com/push/1"}
            sub2 = {**SAMPLE_SUBSCRIPTION, "endpoint": "https://example.com/push/2"}

            client.post("/projects/test-project/push/subscribe", json={"subscription": sub1})
            client.post("/projects/test-project/push/subscribe", json={"subscription": sub2})

            db = sqlite3.connect(db_path)
            rows = db.execute(
                "SELECT subscription_json FROM push_subscriptions WHERE project_slug = ?",
                ("test-project",),
            ).fetchall()
            db.close()
            assert len(rows) == 2
        finally:
            _cleanup(db_fd, db_path)

    def test_does_not_duplicate_same_endpoint(self):
        """Re-subscribing with the same endpoint updates rather than duplicates."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)

            client.post(
                "/projects/test-project/push/subscribe",
                json={"subscription": SAMPLE_SUBSCRIPTION},
            )
            client.post(
                "/projects/test-project/push/subscribe",
                json={"subscription": SAMPLE_SUBSCRIPTION},
            )

            db = sqlite3.connect(db_path)
            rows = db.execute(
                "SELECT subscription_json FROM push_subscriptions WHERE project_slug = ?",
                ("test-project",),
            ).fetchall()
            db.close()
            # Should be 1, not 2 — the same endpoint should not be stored twice
            assert len(rows) == 1
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# DELETE /projects/<slug>/push/subscribe
# ===========================================================================


class TestPushUnsubscribeAuth:
    """Auth gating for DELETE /projects/<slug>/push/subscribe."""

    def test_unauthenticated_redirects(self):
        """Unauthenticated request redirects to /."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.delete(
                "/projects/test-project/push/subscribe",
                json={"endpoint": SAMPLE_SUBSCRIPTION["endpoint"]},
            )
            assert response.status_code == 302
            assert response.headers["Location"] == "/"
        finally:
            _cleanup(db_fd, db_path)

    def test_nonexistent_project_returns_404(self):
        """Authenticated request for nonexistent project returns 404."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            _auth_session(client)
            response = client.delete(
                "/projects/nonexistent/push/subscribe",
                json={"endpoint": SAMPLE_SUBSCRIPTION["endpoint"]},
            )
            assert response.status_code == 404
        finally:
            _cleanup(db_fd, db_path)


class TestPushUnsubscribeSuccess:
    """DELETE /projects/<slug>/push/subscribe removes the subscription."""

    def test_returns_204_on_success(self):
        """Returns 204 on successful unsubscription."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            _insert_subscription(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.delete(
                "/projects/test-project/push/subscribe",
                json={"endpoint": SAMPLE_SUBSCRIPTION["endpoint"]},
            )
            assert response.status_code == 204
        finally:
            _cleanup(db_fd, db_path)

    def test_removes_subscription_from_db(self):
        """The subscription is deleted from push_subscriptions table."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            _insert_subscription(db_path)
            client = app.test_client()
            _auth_session(client)
            client.delete(
                "/projects/test-project/push/subscribe",
                json={"endpoint": SAMPLE_SUBSCRIPTION["endpoint"]},
            )
            db = sqlite3.connect(db_path)
            rows = db.execute(
                "SELECT * FROM push_subscriptions WHERE project_slug = ?",
                ("test-project",),
            ).fetchall()
            db.close()
            assert len(rows) == 0
        finally:
            _cleanup(db_fd, db_path)

    def test_returns_204_even_if_subscription_not_found(self):
        """Returns 204 even when the endpoint doesn't match any subscription (idempotent)."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.delete(
                "/projects/test-project/push/subscribe",
                json={"endpoint": "https://nonexistent.example.com/push"},
            )
            assert response.status_code == 204
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# GET /projects/<slug>/push/vapid-key
# ===========================================================================


class TestVapidKeyAuth:
    """Auth gating for GET /projects/<slug>/push/vapid-key."""

    def test_unauthenticated_redirects(self):
        """Unauthenticated request redirects to /."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.get("/projects/test-project/push/vapid-key")
            assert response.status_code == 302
            assert response.headers["Location"] == "/"
        finally:
            _cleanup(db_fd, db_path)


class TestVapidKeyEndpoint:
    """GET /projects/<slug>/push/vapid-key returns the VAPID public key."""

    def test_returns_200_with_key(self):
        """Returns 200 with JSON containing the VAPID key."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project/push/vapid-key")
            assert response.status_code == 200
            data = response.get_json()
            assert "key" in data
            assert data["key"] == TEST_VAPID_KEY
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# send_push_notification function
# ===========================================================================


class TestSendPushNotification:
    """The send_push_notification function in app/push.py."""

    @patch("app.push.webpush")
    def test_sends_to_all_subscriptions(self, mock_webpush):
        """Calls webpush() for each subscription stored for the project."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            sub1 = {**SAMPLE_SUBSCRIPTION, "endpoint": "https://example.com/push/1"}
            sub2 = {**SAMPLE_SUBSCRIPTION, "endpoint": "https://example.com/push/2"}
            _insert_subscription(db_path, subscription=sub1)
            _insert_subscription(db_path, subscription=sub2)

            from app.push import send_push_notification

            send_push_notification(
                "test-project",
                "Test message",
                db_path,
                "/fake/vapid_private.pem",
                "mailto:test@example.com",
            )

            assert mock_webpush.call_count == 2
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.push.webpush")
    def test_no_subscriptions_no_error(self, mock_webpush):
        """If there are no subscriptions, no push is sent and no error occurs."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)

            from app.push import send_push_notification

            # Should not raise
            send_push_notification(
                "test-project",
                "Test message",
                db_path,
                "/fake/vapid_private.pem",
                "mailto:test@example.com",
            )
            mock_webpush.assert_not_called()
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.push.webpush")
    def test_sends_correct_payload(self, mock_webpush):
        """The push notification payload contains the message text."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            _insert_subscription(db_path)

            from app.push import send_push_notification

            send_push_notification(
                "test-project",
                "Ralph is done building your project.",
                db_path,
                "/fake/vapid_private.pem",
                "mailto:test@example.com",
            )

            mock_webpush.assert_called_once()
            call_kwargs = mock_webpush.call_args
            # The data kwarg should contain the message
            data_arg = call_kwargs.kwargs.get("data")
            assert data_arg is not None
            assert "Ralph is done building your project." in data_arg
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.push.webpush")
    def test_passes_subscription_info_to_webpush(self, mock_webpush):
        """The subscription_info kwarg matches the stored subscription."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            _insert_subscription(db_path)

            from app.push import send_push_notification

            send_push_notification(
                "test-project",
                "Test",
                db_path,
                "/fake/vapid_private.pem",
                "mailto:test@example.com",
            )

            mock_webpush.assert_called_once()
            call_kwargs = mock_webpush.call_args
            sub_info = call_kwargs.kwargs.get("subscription_info")
            assert sub_info is not None
            assert sub_info["endpoint"] == SAMPLE_SUBSCRIPTION["endpoint"]
            assert sub_info["keys"]["p256dh"] == SAMPLE_SUBSCRIPTION["keys"]["p256dh"]
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.push.webpush")
    def test_passes_vapid_private_key(self, mock_webpush):
        """The vapid_private_key kwarg is passed through to webpush."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            _insert_subscription(db_path)

            from app.push import send_push_notification

            send_push_notification(
                "test-project",
                "Test",
                db_path,
                "/my/vapid_private.pem",
                "mailto:test@example.com",
            )

            mock_webpush.assert_called_once()
            call_kwargs = mock_webpush.call_args
            assert call_kwargs.kwargs.get("vapid_private_key") == "/my/vapid_private.pem"
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.push.webpush")
    def test_passes_vapid_claims(self, mock_webpush):
        """The vapid_claims kwarg includes the sub (email) field."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            _insert_subscription(db_path)

            from app.push import send_push_notification

            send_push_notification(
                "test-project",
                "Test",
                db_path,
                "/fake/vapid_private.pem",
                "mailto:test@example.com",
            )

            mock_webpush.assert_called_once()
            call_kwargs = mock_webpush.call_args
            vapid_claims = call_kwargs.kwargs.get("vapid_claims")
            assert vapid_claims is not None
            assert vapid_claims["sub"] == "mailto:test@example.com"
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.push.webpush")
    def test_deletes_stale_subscription_on_410(self, mock_webpush):
        """If webpush() raises WebPushException with 410 status, the subscription is deleted."""
        from pywebpush import WebPushException

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            _insert_subscription(db_path)

            # Simulate a 410 Gone response (subscription expired/unsubscribed)
            response_mock = MagicMock()
            response_mock.status_code = 410
            mock_webpush.side_effect = WebPushException("Gone", response=response_mock)

            from app.push import send_push_notification

            send_push_notification(
                "test-project",
                "Test message",
                db_path,
                "/fake/vapid_private.pem",
                "mailto:test@example.com",
            )

            # The stale subscription should have been removed
            db = sqlite3.connect(db_path)
            rows = db.execute(
                "SELECT * FROM push_subscriptions WHERE project_slug = ?",
                ("test-project",),
            ).fetchall()
            db.close()
            assert len(rows) == 0
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.push.webpush")
    def test_keeps_subscription_on_non_410_error(self, mock_webpush):
        """If webpush() raises WebPushException with non-410 status, subscription is kept."""
        from pywebpush import WebPushException

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            _insert_subscription(db_path)

            response_mock = MagicMock()
            response_mock.status_code = 500
            mock_webpush.side_effect = WebPushException("Server Error", response=response_mock)

            from app.push import send_push_notification

            send_push_notification(
                "test-project",
                "Test message",
                db_path,
                "/fake/vapid_private.pem",
                "mailto:test@example.com",
            )

            # Subscription should still be there
            db = sqlite3.connect(db_path)
            rows = db.execute(
                "SELECT * FROM push_subscriptions WHERE project_slug = ?",
                ("test-project",),
            ).fetchall()
            db.close()
            assert len(rows) == 1
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# Integration: _watch_ralph calls send_push_notification
# ===========================================================================


class TestWatchRalphPushIntegration:
    """When ralph stops, _watch_ralph calls send_push_notification."""

    @patch("app.routes.subprocess.Popen")
    @patch("app.push.send_push_notification")
    def test_all_done_sends_push_notification(self, mock_send_push, mock_popen):
        """When ralph stops with 'all_done', sends push with done message."""
        mock_process = MagicMock()
        mock_process.stdout = iter([b"NO MORE ISSUES LEFT\n"])
        mock_process.wait.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)

            response = client.post("/projects/test-project/ralph/start")
            assert response.status_code == 200

            # Give the background watcher thread time to run
            time.sleep(0.5)

            mock_send_push.assert_called_once()
            call_args = mock_send_push.call_args
            # Should include the slug and a "done" message
            args = call_args[0] if call_args[0] else ()
            kwargs = call_args[1] if call_args[1] else {}
            all_args_str = " ".join(str(a) for a in args) + " ".join(str(v) for v in kwargs.values())
            assert "test-project" in all_args_str
            assert "done" in all_args_str.lower()
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.subprocess.Popen")
    @patch("app.push.send_push_notification")
    def test_human_needed_sends_push_notification(self, mock_send_push, mock_popen):
        """When ralph stops with 'human_needed', sends push with help message."""
        mock_process = MagicMock()
        # Last line is not "NO MORE ISSUES LEFT", so reason = human_needed
        mock_process.stdout = iter([b"HUMAN NEEDED\n"])
        mock_process.wait.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)

            response = client.post("/projects/test-project/ralph/start")
            assert response.status_code == 200

            time.sleep(0.5)

            mock_send_push.assert_called_once()
            call_args = mock_send_push.call_args
            args = call_args[0] if call_args[0] else ()
            kwargs = call_args[1] if call_args[1] else {}
            all_args_str = " ".join(str(a) for a in args) + " ".join(str(v) for v in kwargs.values())
            assert "test-project" in all_args_str
            assert "help" in all_args_str.lower() or "blocked" in all_args_str.lower()
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# Frontend / template: push notification UI elements
# ===========================================================================


class TestPushNotificationUI:
    """Push notification UI elements in the project page HTML."""

    def test_page_includes_manifest_link(self):
        """The project page includes a <link rel='manifest'> tag."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert 'rel="manifest"' in html
        finally:
            _cleanup(db_fd, db_path)

    def test_page_includes_service_worker_registration(self):
        """The project page includes a service worker registration script."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert "serviceWorker" in html
            assert "register" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_page_includes_vapid_public_key_variable(self):
        """The project page includes a VAPID_PUBLIC_KEY JavaScript variable."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert "VAPID_PUBLIC_KEY" in html
        finally:
            _cleanup(db_fd, db_path)

    def test_service_worker_file_served(self):
        """The service worker file is served at /static/sw.js."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.get("/static/sw.js")
            assert response.status_code == 200
            assert "javascript" in response.content_type or "text" in response.content_type
        finally:
            _cleanup(db_fd, db_path)
