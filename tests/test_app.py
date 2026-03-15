import os
import sqlite3
import tempfile

from app import create_app


def test_app_creates():
    app = create_app()
    assert app is not None


def test_index_returns_200():
    app = create_app()
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200


def test_health_returns_ok():
    app = create_app()
    client = app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_init_db_creates_projects_table():
    """DB is initialized on app startup with a projects table."""
    db_fd, db_path = tempfile.mkstemp()
    try:
        create_app({"DATABASE": db_path})
        # Table should already exist after create_app
        db = sqlite3.connect(db_path)
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")
        tables = cursor.fetchall()
        db.close()
        assert len(tables) == 1
    finally:
        os.close(db_fd)
        os.unlink(db_path)
