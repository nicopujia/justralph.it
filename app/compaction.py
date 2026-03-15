"""Automatic session compaction for Ralphy opencode sessions.

Monitors active sessions and triggers summarization when token usage
approaches the context limit (80% of 200,000 tokens).
"""

import logging
import sqlite3
import threading

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONTEXT_LIMIT = 200_000
COMPACTION_THRESHOLD = 0.8
CHECK_INTERVAL = 30  # seconds between checks

# ---------------------------------------------------------------------------
# Module-level state for the monitor thread
# ---------------------------------------------------------------------------

_stop_event = threading.Event()
_monitor_thread = None


# ---------------------------------------------------------------------------
# Token checking
# ---------------------------------------------------------------------------


def check_session_tokens(opencode_url, session_id):
    """Query opencode for the token count of the last assistant message.

    Returns the tokens.total from the last assistant message, or 0 if
    there are no messages, no assistant messages, or on any error.
    """
    try:
        resp = requests.get(
            f"{opencode_url}/session/{session_id}/message",
            timeout=10,
        )
        messages = resp.json()

        # Find the last assistant message
        last_assistant = None
        for msg in messages:
            if msg.get("info", {}).get("role") == "assistant":
                last_assistant = msg

        if last_assistant is None:
            return 0

        return last_assistant["info"]["tokens"]["total"]
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Compaction trigger
# ---------------------------------------------------------------------------


def maybe_compact_session(opencode_url, session_id):
    """Trigger compaction if the session is above the token threshold.

    Returns True if compaction was triggered, False otherwise.
    """
    tokens = check_session_tokens(opencode_url, session_id)

    if tokens < CONTEXT_LIMIT * COMPACTION_THRESHOLD:
        return False

    try:
        requests.post(
            f"{opencode_url}/session/{session_id}/summarize",
            json={"providerID": "anthropic", "modelID": "claude-opus-4-1"},
            timeout=30,
        )
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Background monitor
# ---------------------------------------------------------------------------


def _monitor_loop(db_path, opencode_url, stop_event):
    """Background loop that checks all active sessions for compaction."""
    while not stop_event.is_set():
        try:
            db = sqlite3.connect(db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT opencode_session_id FROM projects WHERE opencode_session_id IS NOT NULL"
            ).fetchall()
            db.close()

            for row in rows:
                session_id = row["opencode_session_id"]
                maybe_compact_session(opencode_url, session_id)
        except Exception:
            logger.exception("Error in compaction monitor loop")

        stop_event.wait(CHECK_INTERVAL)


def start_compaction_monitor(app):
    """Start the compaction monitor daemon thread.

    Reads DATABASE and OPENCODE_URL from the Flask app config.
    """
    global _monitor_thread, _stop_event

    # Stop any existing monitor thread first
    stop_compaction_monitor()

    _stop_event = threading.Event()

    db_path = app.config["DATABASE"]
    opencode_url = app.config.get("OPENCODE_URL", "http://127.0.0.1:4096")

    _monitor_thread = threading.Thread(
        target=_monitor_loop,
        args=(db_path, opencode_url, _stop_event),
        name="compaction-monitor",
        daemon=True,
    )
    _monitor_thread.start()


def stop_compaction_monitor():
    """Stop the compaction monitor thread gracefully."""
    global _monitor_thread

    _stop_event.set()

    if _monitor_thread is not None:
        _monitor_thread.join(timeout=5)
        _monitor_thread = None
