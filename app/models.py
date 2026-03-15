import sqlite3

from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            slug TEXT UNIQUE,
            repo_url TEXT,
            description TEXT,
            vps_path TEXT,
            opencode_session_id TEXT,
            bdui_port INTEGER,
            status TEXT DEFAULT 'draft',
            ralph_running INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # Migrate existing tables: add columns if they don't exist
    _add_column_if_missing(db, "projects", "description", "TEXT")
    _add_column_if_missing(db, "projects", "vps_path", "TEXT")
    _add_column_if_missing(db, "projects", "opencode_session_id", "TEXT")
    _add_column_if_missing(db, "projects", "bdui_port", "INTEGER")
    db.commit()


def _add_column_if_missing(db, table, column, col_type):
    """Add a column to a table if it doesn't already exist."""
    cursor = db.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in cursor.fetchall()}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
