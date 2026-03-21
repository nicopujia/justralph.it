"""GitHub OAuth flow + in-memory session store."""

import logging
import os
import uuid

import httpx

import server.db as db

logger = logging.getLogger(__name__)

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

# session_token -> {github_token, github_user}
_sessions: dict[str, dict] = {}


def get_github_auth_url() -> str:
    """Return GitHub OAuth authorize URL."""
    return f"{GITHUB_AUTHORIZE_URL}?client_id={GITHUB_CLIENT_ID}&scope=read:user"


async def exchange_code_for_token(code: str) -> str:
    """Exchange auth code for GitHub access token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GITHUB_TOKEN_URL,
            json={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    token = data.get("access_token")
    if not token:
        raise ValueError(f"GitHub OAuth error: {data.get('error_description', data)}")
    return token


async def get_github_user(token: str) -> dict:
    """Fetch GitHub user info (login, name, avatar_url)."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            GITHUB_USER_URL,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    return {
        "login": data.get("login"),
        "name": data.get("name"),
        "avatar_url": data.get("avatar_url"),
    }


def create_user_session(github_token: str, github_user: dict) -> str:
    """Store session, return a new session token (uuid)."""
    session_token = str(uuid.uuid4())
    _sessions[session_token] = {
        "github_token": github_token,
        "github_user": github_user,
    }
    db.save_user(
        session_token,
        github_token,
        github_user.get("login", ""),
        github_user.get("name"),
        github_user.get("avatar_url"),
    )
    return session_token


def get_user_session(session_token: str) -> dict | None:
    """Look up session by token. Returns {github_token, github_user} or None."""
    cached = _sessions.get(session_token)
    if cached:
        return cached
    # Fall back to DB
    row = db.load_user(session_token)
    if not row:
        return None
    session_data = {
        "github_token": row["github_token"],
        "github_user": {
            "login": row["login"],
            "name": row["name"],
            "avatar_url": row["avatar_url"],
        },
    }
    _sessions[session_token] = session_data
    return session_data
