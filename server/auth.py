"""GitHub OAuth authentication routes."""

import os

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

auth_router = APIRouter()

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")


@auth_router.get("/github")
def github_login():
    """Redirect user to GitHub OAuth authorize page."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GITHUB_CLIENT_ID not configured")
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&scope=read:user"
    )
    return RedirectResponse(url)


@auth_router.get("/github/callback")
async def github_callback(code: str | None = None):
    """Exchange OAuth code for access token, redirect to frontend with token."""
    if not code:
        raise HTTPException(status_code=400, detail="Missing code parameter")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )

    data = resp.json()
    token = data.get("access_token")
    if not token:
        error = data.get("error_description", "Token exchange failed")
        raise HTTPException(status_code=400, detail=error)

    return RedirectResponse(f"{FRONTEND_URL}?token={token}")


@auth_router.get("/me")
async def get_current_user(request: Request):
    """Return GitHub user info from Bearer token."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth.removeprefix("Bearer ")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = resp.json()
    return {
        "username": user.get("login"),
        "avatar": user.get("avatar_url"),
        "name": user.get("name"),
    }
