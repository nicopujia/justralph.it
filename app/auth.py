"""Auth blueprint: GitHub App installation-based authentication."""

import secrets

from flask import Blueprint, current_app, redirect, request, session

from app import github

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/github")
def github_redirect():
    """Redirect to GitHub App installation page with a random state."""
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    slug = current_app.config["GITHUB_APP_SLUG"]
    return redirect(f"https://github.com/apps/{slug}/installations/new?state={state}")


@bp.route("/callback")
def callback():
    """Handle the GitHub App installation callback."""
    installation_id = request.args.get("installation_id")
    state = request.args.get("state")

    if not installation_id:
        return "Missing installation_id", 400

    if state != session.get("oauth_state"):
        return "Invalid state", 400

    # Validate the installation via GitHub API
    installation = github.get_installation(installation_id)
    login = installation["account"]["login"]

    if login != "nicopujia":
        return "Not available yet.", 200

    # Create installation access token
    token_data = github.create_installation_token(installation_id)

    # Store auth info in session
    session["user"] = login
    session["installation_id"] = installation_id
    session["installation_token"] = token_data["token"]
    session["token_expires_at"] = token_data["expires_at"]

    # Clean up oauth state
    session.pop("oauth_state", None)

    return redirect("/projects")


@bp.route("/logout")
def logout():
    """Clear session and redirect to index."""
    session.clear()
    return redirect("/")
