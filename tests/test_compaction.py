"""Tests for automatic Ralphy session compaction (TDD — written before implementation).

Feature: Monitor Ralphy opencode sessions. When a session approaches the
context limit (80% of 200,000 tokens = 160,000), automatically call
POST /session/:id/summarize on the opencode server. This happens silently
in the background.

Module: app/compaction.py

Functions:
- check_session_tokens(opencode_url, session_id) — returns token count from last assistant message
- maybe_compact_session(opencode_url, session_id) — triggers compaction if above threshold
- start_compaction_monitor(app) — starts daemon thread that checks all active sessions
- stop_compaction_monitor() — gracefully stops the monitor thread

Constants:
- CONTEXT_LIMIT = 200_000
- COMPACTION_THRESHOLD = 0.8
- CHECK_INTERVAL = 30
"""

import os
import sqlite3
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch

from app import create_app

# ---------------------------------------------------------------------------
# Helpers (same pattern as test_recovery.py)
# ---------------------------------------------------------------------------


def _make_app(**extra_config):
    """Create app with a temp DB and return (app, db_path, db_fd).

    Patches recover_processes during app creation so we don't trigger
    side effects.
    """
    db_fd, db_path = tempfile.mkstemp()
    with patch("app.recovery.recover_processes"):
        app = create_app({"DATABASE": db_path, "TESTING": True, **extra_config})
    return app, db_path, db_fd


def _cleanup(db_fd, db_path):
    os.close(db_fd)
    os.unlink(db_path)


def _insert_project(
    db_path,
    name="test-project",
    slug="test-project",
    opencode_session_id="sess-abc-123",
    vps_path="/home/nico/projects/test-project",
    ralph_running=0,
    bdui_port=None,
):
    """Insert a project directly into the DB."""
    db = sqlite3.connect(db_path)
    db.execute(
        """INSERT INTO projects
           (name, slug, opencode_session_id, vps_path, ralph_running, bdui_port)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name, slug, opencode_session_id, vps_path, ralph_running, bdui_port),
    )
    db.commit()
    db.close()


def _make_assistant_message(session_id, msg_id, total_tokens):
    """Build an assistant message dict matching the opencode API format."""
    return {
        "info": {
            "id": msg_id,
            "sessionID": session_id,
            "role": "assistant",
            "tokens": {
                "total": total_tokens,
                "input": total_tokens - 5000,
                "output": 5000,
                "reasoning": 0,
                "cache": {"read": 40000, "write": 5000},
            },
        },
        "parts": [],
    }


def _make_user_message(session_id, msg_id):
    """Build a user message dict matching the opencode API format."""
    return {
        "info": {
            "id": msg_id,
            "sessionID": session_id,
            "role": "user",
        },
        "parts": [],
    }


# ===========================================================================
# Constants
# ===========================================================================


class TestConstants:
    """Verify compaction constants are set correctly."""

    def test_context_limit(self):
        """CONTEXT_LIMIT is 200,000."""
        from app.compaction import CONTEXT_LIMIT

        assert CONTEXT_LIMIT == 200_000

    def test_compaction_threshold(self):
        """COMPACTION_THRESHOLD is 0.8 (80%)."""
        from app.compaction import COMPACTION_THRESHOLD

        assert COMPACTION_THRESHOLD == 0.8

    def test_check_interval(self):
        """CHECK_INTERVAL is 30 seconds."""
        from app.compaction import CHECK_INTERVAL

        assert CHECK_INTERVAL == 30


# ===========================================================================
# check_session_tokens
# ===========================================================================


class TestCheckSessionTokens:
    """check_session_tokens queries opencode and returns token count."""

    @patch("app.compaction.requests.get")
    def test_returns_token_count_from_last_assistant_message(self, mock_get):
        """Returns tokens.total from the last assistant message."""
        from app.compaction import check_session_tokens

        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value=[
                    _make_user_message("sess-123", "msg1"),
                    _make_assistant_message("sess-123", "msg2", 150000),
                ]
            ),
        )

        result = check_session_tokens("http://localhost:4096", "sess-123")
        assert result == 150000
        mock_get.assert_called_once_with("http://localhost:4096/session/sess-123/message", timeout=10)

    @patch("app.compaction.requests.get")
    def test_returns_0_when_no_messages(self, mock_get):
        """Returns 0 when the message list is empty."""
        from app.compaction import check_session_tokens

        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value=[]),
        )

        result = check_session_tokens("http://localhost:4096", "sess-123")
        assert result == 0

    @patch("app.compaction.requests.get")
    def test_returns_0_when_no_assistant_messages(self, mock_get):
        """Returns 0 when there are only user messages (no assistant)."""
        from app.compaction import check_session_tokens

        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value=[
                    _make_user_message("sess-123", "msg1"),
                    _make_user_message("sess-123", "msg2"),
                ]
            ),
        )

        result = check_session_tokens("http://localhost:4096", "sess-123")
        assert result == 0

    @patch("app.compaction.requests.get")
    def test_returns_0_on_http_error(self, mock_get):
        """Returns 0 on HTTP error (graceful failure)."""
        from app.compaction import check_session_tokens

        mock_get.side_effect = Exception("Connection refused")

        result = check_session_tokens("http://localhost:4096", "sess-123")
        assert result == 0

    @patch("app.compaction.requests.get")
    def test_uses_last_assistant_message_not_first(self, mock_get):
        """Uses the LAST assistant message's tokens.total, not the first."""
        from app.compaction import check_session_tokens

        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value=[
                    _make_user_message("sess-123", "msg1"),
                    _make_assistant_message("sess-123", "msg2", 50000),
                    _make_user_message("sess-123", "msg3"),
                    _make_assistant_message("sess-123", "msg4", 150000),
                ]
            ),
        )

        result = check_session_tokens("http://localhost:4096", "sess-123")
        assert result == 150000


# ===========================================================================
# maybe_compact_session
# ===========================================================================


class TestMaybeCompactSession:
    """maybe_compact_session triggers compaction when above threshold."""

    @patch("app.compaction.requests.post")
    @patch("app.compaction.check_session_tokens")
    def test_triggers_compaction_at_threshold(self, mock_check, mock_post):
        """Triggers compaction when tokens >= 160,000 (CONTEXT_LIMIT * COMPACTION_THRESHOLD)."""
        from app.compaction import maybe_compact_session

        mock_check.return_value = 160000
        mock_post.return_value = MagicMock(status_code=200)

        result = maybe_compact_session("http://localhost:4096", "sess-123")

        assert result is True
        mock_post.assert_called_once()

    @patch("app.compaction.requests.post")
    @patch("app.compaction.check_session_tokens")
    def test_does_not_trigger_below_threshold(self, mock_check, mock_post):
        """Does NOT trigger compaction when tokens < 160,000."""
        from app.compaction import maybe_compact_session

        mock_check.return_value = 100000

        result = maybe_compact_session("http://localhost:4096", "sess-123")

        assert result is False
        mock_post.assert_not_called()

    @patch("app.compaction.requests.post")
    @patch("app.compaction.check_session_tokens")
    def test_returns_true_when_compaction_triggered(self, mock_check, mock_post):
        """Returns True when compaction was triggered."""
        from app.compaction import maybe_compact_session

        mock_check.return_value = 180000
        mock_post.return_value = MagicMock(status_code=200)

        result = maybe_compact_session("http://localhost:4096", "sess-123")
        assert result is True

    @patch("app.compaction.requests.post")
    @patch("app.compaction.check_session_tokens")
    def test_returns_false_below_threshold(self, mock_check, mock_post):
        """Returns False when below threshold."""
        from app.compaction import maybe_compact_session

        mock_check.return_value = 50000

        result = maybe_compact_session("http://localhost:4096", "sess-123")
        assert result is False

    @patch("app.compaction.requests.post")
    @patch("app.compaction.check_session_tokens")
    def test_returns_false_on_error(self, mock_check, mock_post):
        """Returns False on error (graceful failure)."""
        from app.compaction import maybe_compact_session

        mock_check.return_value = 180000
        mock_post.side_effect = Exception("Connection refused")

        result = maybe_compact_session("http://localhost:4096", "sess-123")
        assert result is False

    @patch("app.compaction.requests.post")
    @patch("app.compaction.check_session_tokens")
    def test_calls_summarize_with_correct_body(self, mock_check, mock_post):
        """Calls POST /session/:id/summarize with correct provider/model body."""
        from app.compaction import maybe_compact_session

        mock_check.return_value = 170000
        mock_post.return_value = MagicMock(status_code=200)

        maybe_compact_session("http://localhost:4096", "sess-123")

        mock_post.assert_called_once_with(
            "http://localhost:4096/session/sess-123/summarize",
            json={"providerID": "anthropic", "modelID": "claude-opus-4-1"},
            timeout=30,
        )

    @patch("app.compaction.requests.post")
    @patch("app.compaction.check_session_tokens")
    def test_does_not_trigger_at_threshold_minus_1(self, mock_check, mock_post):
        """Does NOT trigger at exactly threshold-1 (159,999 tokens)."""
        from app.compaction import maybe_compact_session

        mock_check.return_value = 159999

        result = maybe_compact_session("http://localhost:4096", "sess-123")

        assert result is False
        mock_post.assert_not_called()

    @patch("app.compaction.requests.post")
    @patch("app.compaction.check_session_tokens")
    def test_triggers_at_exact_threshold(self, mock_check, mock_post):
        """DOES trigger at exactly threshold (160,000 tokens)."""
        from app.compaction import maybe_compact_session

        mock_check.return_value = 160000
        mock_post.return_value = MagicMock(status_code=200)

        result = maybe_compact_session("http://localhost:4096", "sess-123")

        assert result is True
        mock_post.assert_called_once()


# ===========================================================================
# Compaction monitor (start/stop daemon thread)
# ===========================================================================


class TestCompactionMonitor:
    """start/stop_compaction_monitor manage a background daemon thread."""

    @patch("app.compaction.maybe_compact_session")
    def test_start_creates_daemon_thread(self, mock_compact):
        """start_compaction_monitor starts a daemon thread."""
        from app.compaction import start_compaction_monitor, stop_compaction_monitor

        app, db_path, db_fd = _make_app()
        try:
            start_compaction_monitor(app)
            # Give the thread a moment to start
            time.sleep(0.1)

            # Find compaction threads
            compaction_threads = [t for t in threading.enumerate() if t.name == "compaction-monitor"]
            assert len(compaction_threads) == 1
            assert compaction_threads[0].daemon is True

            stop_compaction_monitor()
            # Wait for thread to stop
            time.sleep(0.2)
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.compaction.maybe_compact_session")
    def test_monitor_checks_projects_with_session_id(self, mock_compact):
        """Monitor calls maybe_compact_session for projects with opencode_session_id."""
        from app.compaction import (
            CHECK_INTERVAL,
            start_compaction_monitor,
            stop_compaction_monitor,
        )

        app, db_path, db_fd = _make_app(
            OPENCODE_URL="http://localhost:4096",
        )
        try:
            _insert_project(
                db_path,
                name="proj-a",
                slug="proj-a",
                opencode_session_id="sess-aaa",
            )
            _insert_project(
                db_path,
                name="proj-b",
                slug="proj-b",
                opencode_session_id="sess-bbb",
            )

            # Patch CHECK_INTERVAL to something tiny so the loop runs quickly
            with patch("app.compaction.CHECK_INTERVAL", 0.05):
                start_compaction_monitor(app)
                time.sleep(0.2)
                stop_compaction_monitor()
                time.sleep(0.1)

            # Both projects should have been checked
            session_ids_checked = [call.args[1] for call in mock_compact.call_args_list]
            assert "sess-aaa" in session_ids_checked
            assert "sess-bbb" in session_ids_checked
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.compaction.maybe_compact_session")
    def test_monitor_skips_projects_without_session_id(self, mock_compact):
        """Monitor skips projects without opencode_session_id."""
        from app.compaction import start_compaction_monitor, stop_compaction_monitor

        app, db_path, db_fd = _make_app(
            OPENCODE_URL="http://localhost:4096",
        )
        try:
            _insert_project(
                db_path,
                name="has-session",
                slug="has-session",
                opencode_session_id="sess-aaa",
            )
            _insert_project(
                db_path,
                name="no-session",
                slug="no-session",
                opencode_session_id=None,
            )

            with patch("app.compaction.CHECK_INTERVAL", 0.05):
                start_compaction_monitor(app)
                time.sleep(0.2)
                stop_compaction_monitor()
                time.sleep(0.1)

            # Only the project with a session ID should be checked
            session_ids_checked = [call.args[1] for call in mock_compact.call_args_list]
            assert "sess-aaa" in session_ids_checked
            assert None not in session_ids_checked
            # Make sure no call was made with the None session
            for call in mock_compact.call_args_list:
                assert call.args[1] is not None
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.compaction.maybe_compact_session")
    def test_stop_compaction_monitor_stops_thread(self, mock_compact):
        """stop_compaction_monitor sets a stop event and the thread exits."""
        from app.compaction import start_compaction_monitor, stop_compaction_monitor

        app, db_path, db_fd = _make_app()
        try:
            with patch("app.compaction.CHECK_INTERVAL", 0.05):
                start_compaction_monitor(app)
                time.sleep(0.1)

                # Thread should be running
                compaction_threads = [t for t in threading.enumerate() if t.name == "compaction-monitor"]
                assert len(compaction_threads) == 1

                stop_compaction_monitor()
                time.sleep(0.2)

                # Thread should have stopped
                compaction_threads = [t for t in threading.enumerate() if t.name == "compaction-monitor"]
                assert len(compaction_threads) == 0
        finally:
            _cleanup(db_fd, db_path)
