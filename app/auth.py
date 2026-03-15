"""Auth blueprint: GitHub OAuth authentication."""

import secrets

import requests
from flask import Blueprint, current_app, redirect, request, session

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/github")
def github_redirect():
    """Redirect to GitHub OAuth authorize URL."""
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    params = (
        f"client_id={current_app.config['GITHUB_CLIENT_ID']}"
        f"&scope=repo+read%3Auser"
        f"&state={state}"
        f"&redirect_uri=https%3A%2F%2Fjustralph.it%2Fauth%2Fcallback"
    )
    return redirect(f"https://github.com/login/oauth/authorize?{params}")


@bp.route("/callback")
def callback():
    """Handle the GitHub OAuth callback.

    Exchanges the authorization code for an access token,
    fetches the authenticated user, and stores credentials in session.
    """
    code = request.args.get("code")
    state = request.args.get("state")

    if not code:
        return "Missing code", 400

    if state != session.get("oauth_state"):
        return "Invalid state", 400

    # Exchange code for access token
    token_resp = requests.post(
        "https://github.com/login/oauth/access_token",
        json={
            "client_id": current_app.config["GITHUB_CLIENT_ID"],
            "client_secret": current_app.config["GITHUB_CLIENT_SECRET"],
            "code": code,
        },
        headers={"Accept": "application/json"},
        timeout=10,
    )
    token_data = token_resp.json()
    access_token = token_data.get("access_token")

    if not access_token:
        return "Failed to get access token", 400

    # Fetch authenticated user
    user_resp = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"token {access_token}"},
        timeout=10,
    )
    login = user_resp.json().get("login")

    if login != "nicopujia":
        return "Not available yet.", 200

    # Store auth info in session
    session["user"] = login
    session["github_token"] = access_token

    # Clean up oauth state
    session.pop("oauth_state", None)

    return redirect("/projects")


@bp.route("/logout")
def logout():
    """Clear session and redirect to index."""
    session.clear()
    return redirect("/")
