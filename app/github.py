"""GitHub App API helpers: JWT generation and installation management."""

import time

import jwt
import requests
from flask import current_app

GITHUB_API = "https://api.github.com"


def generate_jwt():
    """Generate a JWT for authenticating as the GitHub App.

    Returns an RS256 JWT with iss=APP_ID (int), iat=now-60, exp=now+600.
    """
    app_id = current_app.config["GITHUB_APP_ID"]
    pem_path = current_app.config["GITHUB_PRIVATE_KEY_PATH"]

    with open(pem_path, "rb") as f:
        private_key = f.read()

    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 600,
        "iss": str(int(app_id)),
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def get_installation(installation_id):
    """Validate an installation and return its info.

    Calls GET /app/installations/{installation_id} with JWT auth.
    Returns the JSON response dict.
    """
    token = generate_jwt()
    resp = requests.get(
        f"{GITHUB_API}/app/installations/{installation_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def list_installations():
    """List all installations of this GitHub App.

    Calls GET /app/installations with JWT auth.
    Returns a list of installation dicts.
    """
    token = generate_jwt()
    resp = requests.get(
        f"{GITHUB_API}/app/installations",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def create_installation_token(installation_id):
    """Create an installation access token.

    Calls POST /app/installations/{installation_id}/access_tokens with JWT auth.
    Returns the JSON response dict with 'token' and 'expires_at'.
    """
    token = generate_jwt()
    resp = requests.post(
        f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()
