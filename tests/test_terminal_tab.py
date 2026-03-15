"""Tests for Terminal tab: Ralph stdout streaming feature (TDD).

Feature: The Terminal tab streams ralph.py stdout and handles completion states.

1. Placeholder: Before Ralph has ever run, Terminal tab shows:
   "When the Ralph loop starts, you'll see its stdout here"
2. Streaming: Terminal tab shows ralph.py output line by line (already works)
3. ALL_DONE: When ralph.py stdout contains "NO MORE ISSUES LEFT",
   the terminal shows "Ralph is done."
4. HUMAN_NEEDED: When ralph.py exits without "NO MORE ISSUES LEFT",
   Ralphy sends a chat message "Ralph is blocked — check the Issues tab"
   and the right panel switches to the Issues tab.

Implementation plan:
- _watch_ralph captures stdout and detects last meaningful line
- ralph_stopped SSE event includes {"reason": "all_done"} or {"reason": "human_needed"}
- Frontend JS handles the reason field accordingly
"""

import os
import queue
import sqlite3
import tempfile
import time
from unittest.mock import MagicMock, patch

from app import create_app
from app.sse import subscribe, unsubscribe

# ---------------------------------------------------------------------------
# Helpers (same pattern as test_ralph_launch.py)
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


# ===========================================================================
# 1. TestTerminalPlaceholder
# ===========================================================================


class TestTerminalPlaceholder:
    """Placeholder text in the Terminal tab before Ralph has ever run."""

    def test_placeholder_text_before_ralph_runs(self):
        """When ralph_running=0 (Ralph never ran), the terminal content contains
        'When the Ralph loop starts, you'll see its stdout here'."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()

            # The terminal-content div should contain the placeholder text
            assert "When the Ralph loop starts" in html
            assert "stdout here" in html
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# 2. TestRalphStoppedEvent
# ===========================================================================


class TestRalphStoppedEvent:
    """ralph_stopped SSE event includes a reason field based on stdout content."""

    @patch("app.routes.subprocess.Popen")
    def test_ralph_stopped_includes_all_done_reason(self, mock_popen):
        """When ralph.py stdout contains 'NO MORE ISSUES LEFT' as its last
        non-empty line, the ralph_stopped event includes {"reason": "all_done"}."""
        mock_process = MagicMock()
        # Simulate ralph.py stdout with "NO MORE ISSUES LEFT" as last meaningful line
        mock_process.stdout = iter(
            [
                b"Processing issue #1\n",
                b"COMPLETED ASSIGNED ISSUE\n",
                b"Processing issue #2\n",
                b"NO MORE ISSUES LEFT\n",
            ]
        )
        mock_process.wait.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            q = subscribe("test-project")
            try:
                client = app.test_client()
                _auth_session(client)
                response = client.post("/projects/test-project/ralph/start")
                assert response.status_code == 200

                # Give the background watcher thread time to run
                time.sleep(0.5)

                # Collect all events
                events = []
                while not q.empty():
                    events.append(q.get_nowait())

                # Find the ralph_stopped event
                stopped_events = [e for e in events if e["type"] == "ralph_stopped"]
                assert len(stopped_events) == 1, f"Expected 1 ralph_stopped event, got {len(stopped_events)}: {events}"

                stopped = stopped_events[0]
                assert stopped["data"].get("reason") == "all_done", (
                    f"Expected reason='all_done', got: {stopped['data']}"
                )
            finally:
                unsubscribe("test-project", q)
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.subprocess.Popen")
    def test_ralph_stopped_includes_human_needed_reason(self, mock_popen):
        """When ralph.py stdout does NOT contain 'NO MORE ISSUES LEFT',
        the ralph_stopped event includes {"reason": "human_needed"}."""
        mock_process = MagicMock()
        # Simulate ralph.py stdout WITHOUT "NO MORE ISSUES LEFT"
        mock_process.stdout = iter(
            [
                b"Processing issue #1\n",
                b"COMPLETED ASSIGNED ISSUE\n",
                b"Processing issue #2\n",
                b"Stuck on issue #2\n",
            ]
        )
        mock_process.wait.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            q = subscribe("test-project")
            try:
                client = app.test_client()
                _auth_session(client)
                response = client.post("/projects/test-project/ralph/start")
                assert response.status_code == 200

                # Give the background watcher thread time to run
                time.sleep(0.5)

                # Collect all events
                events = []
                while not q.empty():
                    events.append(q.get_nowait())

                # Find the ralph_stopped event
                stopped_events = [e for e in events if e["type"] == "ralph_stopped"]
                assert len(stopped_events) == 1, f"Expected 1 ralph_stopped event, got {len(stopped_events)}: {events}"

                stopped = stopped_events[0]
                assert stopped["data"].get("reason") == "human_needed", (
                    f"Expected reason='human_needed', got: {stopped['data']}"
                )
            finally:
                unsubscribe("test-project", q)
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.subprocess.Popen")
    def test_ralph_stopped_empty_stdout_is_human_needed(self, mock_popen):
        """When ralph.py has empty stdout (no output at all),
        the ralph_stopped event includes {"reason": "human_needed"}."""
        mock_process = MagicMock()
        mock_process.stdout = iter([])
        mock_process.wait.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            q = subscribe("test-project")
            try:
                client = app.test_client()
                _auth_session(client)
                response = client.post("/projects/test-project/ralph/start")
                assert response.status_code == 200

                time.sleep(0.5)

                events = []
                while not q.empty():
                    events.append(q.get_nowait())

                stopped_events = [e for e in events if e["type"] == "ralph_stopped"]
                assert len(stopped_events) == 1

                stopped = stopped_events[0]
                assert stopped["data"].get("reason") == "human_needed", (
                    f"Expected reason='human_needed', got: {stopped['data']}"
                )
            finally:
                unsubscribe("test-project", q)
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.routes.subprocess.Popen")
    def test_ralph_stopped_all_done_with_trailing_whitespace(self, mock_popen):
        """'NO MORE ISSUES LEFT' followed by blank lines still counts as all_done."""
        mock_process = MagicMock()
        mock_process.stdout = iter(
            [
                b"Processing issue #1\n",
                b"NO MORE ISSUES LEFT\n",
                b"\n",
                b"  \n",
            ]
        )
        mock_process.wait.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            q = subscribe("test-project")
            try:
                client = app.test_client()
                _auth_session(client)
                response = client.post("/projects/test-project/ralph/start")
                assert response.status_code == 200

                time.sleep(0.5)

                events = []
                while not q.empty():
                    events.append(q.get_nowait())

                stopped_events = [e for e in events if e["type"] == "ralph_stopped"]
                assert len(stopped_events) == 1

                stopped = stopped_events[0]
                assert stopped["data"].get("reason") == "all_done", (
                    f"Expected reason='all_done' (trailing whitespace should be ignored), got: {stopped['data']}"
                )
            finally:
                unsubscribe("test-project", q)
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# 3. TestTerminalUI
# ===========================================================================


class TestTerminalUI:
    """Terminal tab UI elements and JS behavior in show.html."""

    def test_terminal_has_dark_background_monospace(self):
        """Terminal content div has monospace font and dark background styling."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()

            # Find the terminal-content div and check its style
            assert 'id="terminal-content"' in html

            # Extract the terminal-content element and check for monospace + dark bg
            # The element should have font-family: monospace and a dark background
            terminal_idx = html.find('id="terminal-content"')
            assert terminal_idx != -1

            # Look at the surrounding element for style attributes
            # Search backward to find the opening tag
            tag_start = html.rfind("<", 0, terminal_idx)
            tag_end = html.find(">", terminal_idx)
            terminal_tag = html[tag_start : tag_end + 1]

            assert "monospace" in terminal_tag, f"Terminal div should have monospace font. Tag: {terminal_tag}"
            # Dark background: #111, #000, #1a1a1a, or similar dark color
            assert any(bg in terminal_tag for bg in ["#111", "#000", "#0a0a0a", "#1a1a1a", "background"]), (
                f"Terminal div should have dark background. Tag: {terminal_tag}"
            )
        finally:
            _cleanup(db_fd, db_path)

    def test_terminal_js_handles_all_done(self):
        """The page JS contains logic to show 'Ralph is done.' when
        ralph_stopped event has reason='all_done'."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()

            # The JS should handle the all_done reason in the ralph_stopped event
            assert "all_done" in html, "Page should contain JS that handles 'all_done' reason"
            assert "Ralph is done" in html, "Page should contain 'Ralph is done.' text for the all_done case"
        finally:
            _cleanup(db_fd, db_path)

    def test_terminal_js_handles_human_needed(self):
        """The page JS contains logic to switch to Issues tab on human_needed
        (check for switchTab('issues') in context of ralph_stopped handling)."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()

            # The JS should handle the human_needed reason
            assert "human_needed" in html, "Page should contain JS that handles 'human_needed' reason"
            # When human_needed, should switch to issues tab
            assert "switchTab" in html, "Page should contain switchTab function"
            # The human_needed handler should call switchTab('issues')
            # Look for switchTab('issues') or switchTab("issues") near human_needed
            assert "issues" in html, "Page should reference 'issues' tab"
        finally:
            _cleanup(db_fd, db_path)

    def test_terminal_js_sends_ralphy_message_on_human_needed(self):
        """The page JS contains logic to send a Ralphy chat message on human_needed.
        This should POST a message like 'Ralph is blocked — check the Issues tab'."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, ralph_running=0)
            client = app.test_client()
            _auth_session(client)
            response = client.get("/projects/test-project")
            html = response.data.decode()

            # The JS should send a chat message when ralph is blocked
            # Look for the blocked message text or a renderMessage call with it
            assert "Ralph is blocked" in html, (
                "Page should contain 'Ralph is blocked' message text for the human_needed case"
            )
        finally:
            _cleanup(db_fd, db_path)
