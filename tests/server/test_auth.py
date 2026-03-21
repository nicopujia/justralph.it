"""Unit tests for server.auth session functions."""

import pytest


@pytest.fixture(autouse=True)
def clear_sessions(monkeypatch):
    """Isolate each test: clear in-memory cache and stub out DB calls."""
    from server.auth import _sessions

    _sessions.clear()
    monkeypatch.setattr("server.auth.db.save_user", lambda *a, **kw: None)
    monkeypatch.setattr("server.auth.db.load_user", lambda token: None)
    yield
    _sessions.clear()


GITHUB_USER = {"login": "ralphy", "name": "Ralph", "avatar_url": "https://example.com/avatar.png"}
GITHUB_TOKEN = "gho_test_token_abc"


# ---------------------------------------------------------------------------
# create_user_session
# ---------------------------------------------------------------------------


def test_create_returns_string_token():
    from server.auth import create_user_session

    token = create_user_session(GITHUB_TOKEN, GITHUB_USER)
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_stores_in_memory():
    from server.auth import _sessions, create_user_session

    token = create_user_session(GITHUB_TOKEN, GITHUB_USER)
    assert token in _sessions
    assert _sessions[token]["github_token"] == GITHUB_TOKEN
    assert _sessions[token]["github_user"] == GITHUB_USER


def test_create_unique_tokens():
    from server.auth import create_user_session

    token_a = create_user_session(GITHUB_TOKEN, GITHUB_USER)
    token_b = create_user_session(GITHUB_TOKEN, GITHUB_USER)
    assert token_a != token_b


# ---------------------------------------------------------------------------
# get_user_session
# ---------------------------------------------------------------------------


def test_get_returns_cached_session():
    from server.auth import create_user_session, get_user_session

    token = create_user_session(GITHUB_TOKEN, GITHUB_USER)
    session = get_user_session(token)
    assert session is not None
    assert session["github_token"] == GITHUB_TOKEN
    assert session["github_user"] == GITHUB_USER


def test_get_returns_none_for_unknown():
    from server.auth import get_user_session

    result = get_user_session("does-not-exist")
    assert result is None


def test_get_falls_back_to_db(monkeypatch):
    from server.auth import _sessions, create_user_session, get_user_session

    token = create_user_session(GITHUB_TOKEN, GITHUB_USER)

    # Simulate cache eviction (e.g. server restart)
    _sessions.clear()

    db_row = {
        "github_token": GITHUB_TOKEN,
        "login": GITHUB_USER["login"],
        "name": GITHUB_USER["name"],
        "avatar_url": GITHUB_USER["avatar_url"],
    }
    monkeypatch.setattr("server.auth.db.load_user", lambda t: db_row if t == token else None)

    session = get_user_session(token)
    assert session is not None
    assert session["github_token"] == GITHUB_TOKEN
    assert session["github_user"]["login"] == GITHUB_USER["login"]


def test_get_caches_after_db_lookup(monkeypatch):
    from server.auth import _sessions, create_user_session, get_user_session

    token = create_user_session(GITHUB_TOKEN, GITHUB_USER)
    _sessions.clear()

    db_row = {
        "github_token": GITHUB_TOKEN,
        "login": GITHUB_USER["login"],
        "name": GITHUB_USER["name"],
        "avatar_url": GITHUB_USER["avatar_url"],
    }
    monkeypatch.setattr("server.auth.db.load_user", lambda t: db_row if t == token else None)

    assert token not in _sessions
    get_user_session(token)
    assert token in _sessions


def test_session_data_structure():
    from server.auth import create_user_session, get_user_session

    token = create_user_session(GITHUB_TOKEN, GITHUB_USER)
    session = get_user_session(token)

    assert "github_token" in session
    assert "github_user" in session
    assert session["github_token"] == GITHUB_TOKEN
    assert session["github_user"]["login"] == GITHUB_USER["login"]
    assert session["github_user"]["name"] == GITHUB_USER["name"]
    assert session["github_user"]["avatar_url"] == GITHUB_USER["avatar_url"]
