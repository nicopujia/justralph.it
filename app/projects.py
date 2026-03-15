"""Project creation logic: validate, create GitHub repo, clone, init beads, start bdui, create opencode session."""

import os
import re
import socket
import subprocess

import requests
from flask import current_app

from .models import get_db

GITHUB_API = "https://api.github.com"
PROJECTS_DIR = os.path.expanduser("~/projects")

# GitHub-valid repo name: alphanumeric, hyphens, underscores, dots
REPO_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def validate_repo_name(name):
    """Validate repo name has only GitHub-valid characters. Returns error string or None."""
    if not name or not name.strip():
        return "Repo name is required."
    if not REPO_NAME_RE.match(name):
        return "Invalid repo name. Only alphanumeric characters, hyphens, underscores, and dots are allowed."
    return None


def check_repo_exists_on_github(repo_name, token):
    """Check if a repo already exists on GitHub for the authenticated user. Returns True if it exists."""
    resp = requests.get(
        f"{GITHUB_API}/repos/nicopujia/{repo_name}",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=10,
    )
    return resp.status_code == 200


def check_local_dir_exists(repo_name):
    """Check if a local project directory already exists."""
    return os.path.isdir(os.path.join(PROJECTS_DIR, repo_name))


def check_db_name_exists(repo_name):
    """Check if a project with this name already exists in the database."""
    db = get_db()
    row = db.execute("SELECT id FROM projects WHERE name = ?", (repo_name,)).fetchone()
    return row is not None


GH_CLI = "/home/linuxbrew/.linuxbrew/bin/gh"


def create_github_repo(repo_name, description, token):
    """Create a new GitHub repo via `gh` CLI, then fetch repo info with the installation token.

    Uses the `gh` CLI (authenticated with a PAT) to create the repo, because
    GitHub App installation tokens (ghs_...) cannot call POST /user/repos.
    After creation, uses the installation token to GET /repos/nicopujia/{name}
    for html_url and clone_url.

    Returns a dict with at least 'html_url' and 'clone_url'.
    """
    cmd = [
        GH_CLI,
        "repo",
        "create",
        repo_name,
        "--public",
        "--description",
        description or "",
        "--add-readme",
        "--clone=false",
        "--confirm",
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=30)

    # Fetch repo info using the installation token (which CAN read repos)
    resp = requests.get(
        f"{GITHUB_API}/repos/nicopujia/{repo_name}",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def clone_repo(clone_url, dest_path, token):
    """Clone a GitHub repo to the VPS."""
    # Insert token into clone URL for auth
    auth_url = clone_url.replace("https://", f"https://x-access-token:{token}@")
    subprocess.run(["git", "clone", auth_url, dest_path], check=True, capture_output=True, timeout=60)


def init_beads(project_path):
    """Initialize beads in the project directory with BEADS_DOLT_SHARED_SERVER=1."""
    env = os.environ.copy()
    env["BEADS_DOLT_SHARED_SERVER"] = "1"
    subprocess.run(["bd", "init"], cwd=project_path, check=True, capture_output=True, timeout=30, env=env)


def find_available_port():
    """Find an available port by binding to port 0."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def start_bdui(project_path, port):
    """Start a bdui sidecar process on the given port. Returns the Popen object."""
    return subprocess.Popen(
        ["bdui", "start", "--port", str(port)],
        cwd=project_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def create_opencode_session(repo_name):
    """Create a new opencode session via POST /session. Returns the session ID."""
    opencode_url = current_app.config["OPENCODE_URL"]
    resp = requests.post(
        f"{opencode_url}/session",
        json={"title": repo_name},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def create_project(repo_name, description, token):
    """Full project creation flow. Returns dict with project info.

    Steps:
    1. Check availability (GitHub + local dir + DB)
    2. Create GitHub repo
    3. Clone to ~/projects/<repo_name>/
    4. Init beads
    5. Start bdui sidecar
    6. Create opencode session
    7. Store in DB

    Raises ValueError on validation/availability errors.
    """
    # Availability checks
    if check_repo_exists_on_github(repo_name, token):
        raise ValueError("A GitHub repo with this name already exists.")

    if check_local_dir_exists(repo_name):
        raise ValueError("A local project directory with this name already exists.")

    if check_db_name_exists(repo_name):
        raise ValueError("A project with this name already exists.")

    # Create GitHub repo
    repo_data = create_github_repo(repo_name, description, token)
    repo_url = repo_data["html_url"]
    clone_url = repo_data["clone_url"]

    # Clone
    vps_path = os.path.join(PROJECTS_DIR, repo_name)
    clone_repo(clone_url, vps_path, token)

    # Init beads
    init_beads(vps_path)

    # Start bdui sidecar
    port = find_available_port()
    start_bdui(vps_path, port)

    # Create opencode session
    session_id = create_opencode_session(repo_name)

    # Derive slug from repo name (lowercase)
    slug = repo_name.lower()

    # Store in DB
    db = get_db()
    db.execute(
        """INSERT INTO projects (name, slug, repo_url, description, vps_path, opencode_session_id, bdui_port)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (repo_name, slug, repo_url, description, vps_path, session_id, port),
    )
    db.commit()

    return {"slug": slug}


def delete_github_repo(repo_name, token):
    """Delete a GitHub repo. Best-effort — exceptions are suppressed."""
    try:
        resp = requests.delete(
            f"{GITHUB_API}/repos/nicopujia/{repo_name}",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=15,
        )
    except Exception:
        pass


def stop_bdui(port):
    """Kill the bdui sidecar running on the given port. Best-effort."""
    if port is None:
        return
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        pids = result.stdout.strip().split("\n")
        for pid in pids:
            if pid.strip():
                subprocess.run(["kill", "-9", pid.strip()], timeout=5)
    except Exception:
        pass


def delete_opencode_session(session_id):
    """Delete an opencode session via DELETE /session/<id>. Best-effort."""
    if session_id is None:
        return
    try:
        opencode_url = current_app.config["OPENCODE_URL"]
        requests.delete(f"{opencode_url}/session/{session_id}", timeout=10)
    except Exception:
        pass


def remove_vps_directory(vps_path):
    """Remove the project's VPS directory. Best-effort."""
    if vps_path is None:
        return
    try:
        import shutil

        shutil.rmtree(vps_path)
    except Exception:
        pass
