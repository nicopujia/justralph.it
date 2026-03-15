"""Tests for the chat interface (TDD — written before implementation).

Feature: Wire up the chat panel to the project's opencode session.

Routes:
- GET  /projects/<slug>/chat/history — proxy to opencode GET /session/:id/message
- POST /projects/<slug>/chat/send    — proxy to opencode POST /session/:id/prompt_async
- GET  /projects/<slug>/chat/events  — proxy opencode GET /event SSE, filter by session

First-message behavior:
- When first_message_sent=0, the description is auto-sent and the flag is set to 1.

Chat UI:
- #chat-messages container, #chat-input field, #chat-send button

DB migration:
- first_message_sent column (INTEGER DEFAULT 0) in projects table
"""

import json
import os
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch

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


def _insert_project(
    db_path,
    name="test-project",
    slug="test-project",
    status="draft",
    opencode_session_id="sess-abc-123",
    description="Build a cool app",
    first_message_sent=0,
):
    """Insert a project directly into the DB."""
    db = sqlite3.connect(db_path)
    db.execute(
        """INSERT INTO projects
           (name, slug, status, opencode_session_id, description, first_message_sent)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name, slug, status, opencode_session_id, description, first_message_sent),
    )
    db.commit()
    db.close()


# ===========================================================================
# DB migration test
# ===========================================================================


class TestFirstMessageSentColumn:
    """The projects table must have a first_message_sent column."""

    def test_column_exists_after_init(self):
        """first_message_sent column exists in projects table after migration."""
        app, db_path, db_fd = _make_app()
        try:
            db = sqlite3.connect(db_path)
            cursor = db.execute("PRAGMA table_info(projects)")
            columns = {row[1] for row in cursor.fetchall()}
            db.close()
            assert "first_message_sent" in columns
        finally:
            _cleanup(db_fd, db_path)

    def test_column_defaults_to_zero(self):
        """first_message_sent defaults to 0 for new rows."""
        app, db_path, db_fd = _make_app()
        try:
            db = sqlite3.connect(db_path)
            db.execute("INSERT INTO projects (name, slug) VALUES ('x', 'x')")
            db.commit()
            row = db.execute("SELECT first_message_sent FROM projects WHERE slug='x'").fetchone()
            db.close()
            assert row[0] == 0
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# GET /projects/<slug>/chat/history
# ===========================================================================


class TestChatHistory:
    """GET /projects/<slug>/chat/history — proxy to opencode messages."""

    def test_unauthenticated_redirects(self):
        """Unauthenticated request redirects to /."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.get("/projects/test-project/chat/history")
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
            response = client.get("/projects/nonexistent/chat/history")
            assert response.status_code == 404
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.requests")
    def test_returns_messages_from_opencode(self, mock_requests):
        """Proxies to opencode and returns JSON array of messages."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"},
            ]
            mock_requests.get.return_value = mock_resp

            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project/chat/history")

            assert response.status_code == 200
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["role"] == "user"

            # Verify the correct opencode URL was called
            mock_requests.get.assert_called_once()
            call_url = mock_requests.get.call_args[0][0]
            assert "/session/sess-abc-123/message" in call_url
        finally:
            _cleanup(db_fd, db_path)

    def test_returns_empty_array_when_no_session_id(self):
        """Returns empty array when opencode_session_id is None."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, opencode_session_id=None)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project/chat/history")
            assert response.status_code == 200
            data = response.get_json()
            assert data == []
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# POST /projects/<slug>/chat/send
# ===========================================================================


class TestChatSend:
    """POST /projects/<slug>/chat/send — send message via opencode."""

    def test_unauthenticated_redirects(self):
        """Unauthenticated request redirects to /."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.post(
                "/projects/test-project/chat/send",
                data=json.dumps({"message": "hello"}),
                content_type="application/json",
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
                "/projects/nonexistent/chat/send",
                data=json.dumps({"message": "hello"}),
                content_type="application/json",
            )
            assert response.status_code == 404
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.requests")
    def test_sends_message_to_opencode(self, mock_requests):
        """Posts message to opencode prompt_async endpoint with correct body."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, first_message_sent=1)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_requests.post.return_value = mock_resp

            client = app.test_client()
            _auth_session(client)
            response = client.post(
                "/projects/test-project/chat/send",
                data=json.dumps({"message": "build the thing"}),
                content_type="application/json",
            )

            assert response.status_code == 204

            # Verify opencode was called correctly
            mock_requests.post.assert_called_once()
            call_url = mock_requests.post.call_args[0][0]
            assert "/session/sess-abc-123/prompt_async" in call_url
        finally:
            _cleanup(db_fd, db_path)

    def test_returns_400_for_empty_message(self):
        """Returns 400 when message is empty."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, first_message_sent=1)
            client = app.test_client()
            _auth_session(client)
            response = client.post(
                "/projects/test-project/chat/send",
                data=json.dumps({"message": ""}),
                content_type="application/json",
            )
            assert response.status_code == 400
        finally:
            _cleanup(db_fd, db_path)

    def test_returns_400_when_no_session_id(self):
        """Returns 400 when opencode_session_id is None."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, opencode_session_id=None, first_message_sent=1)
            client = app.test_client()
            _auth_session(client)
            response = client.post(
                "/projects/test-project/chat/send",
                data=json.dumps({"message": "hello"}),
                content_type="application/json",
            )
            assert response.status_code == 400
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.requests")
    def test_first_message_sends_description(self, mock_requests):
        """On first visit (first_message_sent=0), description is auto-sent."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(
                db_path,
                description="Build a todo app",
                first_message_sent=0,
            )
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_requests.post.return_value = mock_resp

            client = app.test_client()
            _auth_session(client)
            response = client.post(
                "/projects/test-project/chat/send",
                data=json.dumps({"message": "hello"}),
                content_type="application/json",
            )

            assert response.status_code == 204

            # The description should have been sent (first call), then the user message
            assert mock_requests.post.call_count == 2

            # Verify first_message_sent was updated to 1
            db = sqlite3.connect(db_path)
            row = db.execute("SELECT first_message_sent FROM projects WHERE slug='test-project'").fetchone()
            db.close()
            assert row[0] == 1
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# GET /projects/<slug>/chat/events
# ===========================================================================


class TestChatEvents:
    """GET /projects/<slug>/chat/events — proxy opencode SSE stream."""

    def test_unauthenticated_redirects(self):
        """Unauthenticated request redirects to /."""
        app, db_path, db_fd = _make_app()
        try:
            client = app.test_client()
            response = client.get("/projects/test-project/chat/events")
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
            response = client.get("/projects/nonexistent/chat/events")
            assert response.status_code == 404
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.requests")
    def test_returns_sse_content_type(self, mock_requests):
        """Response has text/event-stream content type."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)

            # Mock a streaming response from opencode
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            # iter_lines returns an iterator of SSE lines
            mock_resp.iter_lines.return_value = iter(
                [
                    b'data: {"type":"message.part","sessionId":"sess-abc-123","content":"hi"}',
                ]
            )
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_requests.get.return_value = mock_resp

            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project/chat/events")

            assert response.content_type.startswith("text/event-stream")
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.requests")
    def test_filters_events_by_session_id(self, mock_requests):
        """Only SSE events matching the project's session ID pass through."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, opencode_session_id="sess-abc-123")

            matching_event = json.dumps(
                {
                    "type": "message.part",
                    "sessionId": "sess-abc-123",
                    "content": "hello",
                }
            )
            other_event = json.dumps(
                {
                    "type": "message.part",
                    "sessionId": "sess-other-999",
                    "content": "wrong session",
                }
            )

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.iter_lines.return_value = iter(
                [
                    f"data: {matching_event}".encode(),
                    f"data: {other_event}".encode(),
                ]
            )
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_requests.get.return_value = mock_resp

            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project/chat/events")

            # Read the streamed data
            data = response.get_data(as_text=True)
            # The matching event should be present
            assert "sess-abc-123" in data
            # The non-matching event should be filtered out
            assert "sess-other-999" not in data
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# Chat UI elements in show.html
# ===========================================================================


class TestChatUI:
    """Chat panel elements in the project page HTML."""

    def test_chat_messages_container_exists(self):
        """Chat panel has a messages container with id='chat-messages'."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert 'id="chat-messages"' in html
        finally:
            _cleanup(db_fd, db_path)

    def test_chat_input_field_exists(self):
        """Chat panel has an input field with id='chat-input'."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert 'id="chat-input"' in html
        finally:
            _cleanup(db_fd, db_path)

    def test_chat_send_button_exists(self):
        """Chat panel has a send button with id='chat-send'."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()
            assert 'id="chat-send"' in html
        finally:
            _cleanup(db_fd, db_path)
