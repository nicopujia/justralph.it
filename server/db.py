"""SQLite persistence for sessions, users, chat messages, and chat state."""

import json
import os
import sqlite3
import time

_db_path = "/tmp/ralph-sessions/ralph.db"


def _get_conn() -> sqlite3.Connection:
    """Create a new connection per call (thread-safe for demo)."""
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables and DB directory if needed."""
    os.makedirs(os.path.dirname(_db_path), exist_ok=True)
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            token TEXT PRIMARY KEY,
            github_token TEXT NOT NULL,
            login TEXT NOT NULL,
            name TEXT,
            avatar_url TEXT,
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            base_dir TEXT NOT NULL,
            github_url TEXT DEFAULT '',
            status TEXT DEFAULT 'ready',
            created_at REAL NOT NULL,
            name TEXT DEFAULT '',
            share_token TEXT DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at REAL NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS chat_state (
            session_id TEXT PRIMARY KEY,
            confidence TEXT DEFAULT '{}',
            relevance TEXT DEFAULT '{}',
            ready INTEGER DEFAULT 0,
            weighted_readiness REAL DEFAULT 0,
            tasks TEXT,
            project TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS tool_invocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            tool TEXT NOT NULL,
            mode TEXT NOT NULL,
            elapsed_ms INTEGER,
            model TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );
    """)
    # Migrate existing DBs: add columns if absent.
    for ddl in [
        "ALTER TABLE sessions ADD COLUMN name TEXT DEFAULT ''",
        "ALTER TABLE sessions ADD COLUMN share_token TEXT DEFAULT NULL",
    ]:
        try:
            conn.execute(ddl)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.close()


# -- Sessions ------------------------------------------------------------------


def save_session(
    id: str, base_dir: str, github_url: str, status: str, created_at: float, name: str = ""
) -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO sessions (id, base_dir, github_url, status, created_at, name) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (id, base_dir, github_url, status, created_at, name),
    )
    conn.commit()
    conn.close()


def load_session(id: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_sessions() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM sessions").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_session_status(id: str, status: str) -> None:
    conn = _get_conn()
    conn.execute("UPDATE sessions SET status = ? WHERE id = ?", (status, id))
    conn.commit()
    conn.close()


def update_session_name(id: str, name: str) -> None:
    conn = _get_conn()
    conn.execute("UPDATE sessions SET name = ? WHERE id = ?", (name, id))
    conn.commit()
    conn.close()


def delete_session(id: str) -> None:
    """Delete session and all related data."""
    conn = _get_conn()
    conn.execute("DELETE FROM chat_state WHERE session_id = ?", (id,))
    conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (id,))
    conn.execute("DELETE FROM tool_invocations WHERE session_id = ?", (id,))
    conn.execute("DELETE FROM sessions WHERE id = ?", (id,))
    conn.commit()
    conn.close()


# -- Users ---------------------------------------------------------------------


def save_user(
    token: str,
    github_token: str,
    login: str,
    name: str | None,
    avatar_url: str | None,
) -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO users (token, github_token, login, name, avatar_url, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (token, github_token, login, name, avatar_url, time.time()),
    )
    conn.commit()
    conn.close()


def load_user(token: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE token = ?", (token,)).fetchone()
    conn.close()
    return dict(row) if row else None


# -- Chat messages -------------------------------------------------------------


def save_chat_message(session_id: str, role: str, content: str) -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content, created_at) "
        "VALUES (?, ?, ?, ?)",
        (session_id, role, content, time.time()),
    )
    conn.commit()
    conn.close()


def load_chat_messages(session_id: str) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_chat_messages(session_id: str) -> None:
    conn = _get_conn()
    conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()


# -- Chat state ----------------------------------------------------------------


def save_chat_state(
    session_id: str,
    confidence: dict,
    relevance: dict,
    ready: bool,
    weighted_readiness: float,
    tasks: list | None,
    project: dict | None,
) -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO chat_state "
        "(session_id, confidence, relevance, ready, weighted_readiness, tasks, project) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            session_id,
            json.dumps(confidence),
            json.dumps(relevance),
            int(ready),
            weighted_readiness,
            json.dumps(tasks) if tasks is not None else None,
            json.dumps(project) if project is not None else None,
        ),
    )
    conn.commit()
    conn.close()


def load_chat_state(session_id: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM chat_state WHERE session_id = ?", (session_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["confidence"] = json.loads(d["confidence"])
    d["relevance"] = json.loads(d["relevance"])
    d["ready"] = bool(d["ready"])
    d["tasks"] = json.loads(d["tasks"]) if d["tasks"] else None
    d["project"] = json.loads(d["project"]) if d["project"] else None
    return d


# -- Share tokens --------------------------------------------------------------


def set_share_token(session_id: str, token: str) -> None:
    """Persist share token for a session."""
    conn = _get_conn()
    conn.execute(
        "UPDATE sessions SET share_token = ? WHERE id = ?", (token, session_id)
    )
    conn.commit()
    conn.close()


def get_session_by_share_token(token: str) -> dict | None:
    """Return the session row matching share_token, or None."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM sessions WHERE share_token = ?", (token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# -- Last chat timestamp -------------------------------------------------------


def get_last_chat_timestamp(session_id: str) -> float | None:
    """Return MAX(created_at) from chat_messages for session, or None."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT MAX(created_at) as ts FROM chat_messages WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    conn.close()
    return row["ts"] if row and row["ts"] else None


# -- Tool invocations ----------------------------------------------------------


def save_tool_invocation(session_id: str, tool: str, mode: str, elapsed_ms: int = 0, model: str = "") -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT INTO tool_invocations (session_id, tool, mode, elapsed_ms, model, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, tool, mode, elapsed_ms, model, time.time()),
    )
    conn.commit()
    conn.close()


def load_tool_invocations(session_id: str) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM tool_invocations WHERE session_id = ? ORDER BY id ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
