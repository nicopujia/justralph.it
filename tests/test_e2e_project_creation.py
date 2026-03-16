"""E2E test for the full project creation flow against real services.

This test hits real GitHub, real opencode, real bdui, and real beads.
It creates a GitHub repo, clones it, initializes beads, starts bdui,
creates an opencode session, and verifies everything end-to-end.

NO MOCKING — every step runs against the live VPS environment.

Requirements:
- `gh` CLI authenticated with a token that has `repo` and `delete_repo` scopes
- opencode running at http://127.0.0.1:4096
- `bd` at ~/.local/bin/bd
- `bdui` at ~/.npm-global/bin/bdui
"""

import os
import shutil
import sqlite3
import subprocess
import tempfile
import time

import pytest
import requests

from app import create_app

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GITHUB_API = "https://api.github.com"
GITHUB_USERNAME = "nicopujia"
OPENCODE_URL = "http://127.0.0.1:4096"
PROJECTS_DIR = os.path.expanduser("~/projects")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_github_token():
    """Get a real GitHub token from the gh CLI. Skips test if unavailable."""
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        pytest.skip("gh CLI is not installed")
    except subprocess.TimeoutExpired:
        pytest.skip("gh auth token timed out")

    if result.returncode != 0:
        pytest.skip(f"gh auth token failed: {result.stderr.strip()}")

    token = result.stdout.strip()
    if not token:
        pytest.skip("gh auth token returned empty token")

    return token


def _make_app(db_path):
    """Create app with the given temp DB path."""
    app = create_app({"DATABASE": db_path, "TESTING": True})
    return app


def _auth_session(client, token):
    """Set session vars with the REAL GitHub token."""
    with client.session_transaction() as sess:
        sess["user"] = GITHUB_USERNAME
        sess["github_token"] = token


def _get_project_by_slug(db_path, slug):
    """Fetch a single project row by slug."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    db.close()
    return row


def _github_repo_exists(repo_name, token):
    """Check if a GitHub repo exists via the API."""
    resp = requests.get(
        f"{GITHUB_API}/repos/{GITHUB_USERNAME}/{repo_name}",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=10,
    )
    return resp.status_code == 200


def _delete_github_repo(repo_name, token):
    """Delete a GitHub repo via the API, falling back to gh CLI. Best-effort."""
    try:
        resp = requests.delete(
            f"{GITHUB_API}/repos/{GITHUB_USERNAME}/{repo_name}",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=15,
        )
        if resp.status_code == 204:
            return
    except Exception:
        pass
    # Fallback: try gh CLI (may have different auth)
    try:
        subprocess.run(
            ["gh", "repo", "delete", f"{GITHUB_USERNAME}/{repo_name}", "--yes"],
            capture_output=True,
            timeout=15,
        )
    except Exception:
        pass


def _kill_process_on_port(port):
    """Kill any process listening on the given port. Best-effort."""
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


def _delete_opencode_session(session_id):
    """Delete an opencode session via API. Best-effort."""
    if session_id is None:
        return
    try:
        requests.delete(f"{OPENCODE_URL}/session/{session_id}", timeout=10)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# E2E Test: Full project creation flow
# ---------------------------------------------------------------------------


class TestE2EProjectCreation:
    """End-to-end test for the full project creation flow against real services."""

    def test_full_project_creation_flow(self):
        """Submit the new project form and verify every step of the creation pipeline.

        Steps verified:
        1. POST /projects/new redirects to /projects/<slug>
        2. GitHub repo is created
        3. Project directory is cloned to ~/projects/<repo_name>/
        4. Beads is initialized (.beads/ directory exists)
        5. bdui sidecar is started (process running on the stored port)
        6. Opencode session is created (session exists via API)
        7. Project is stored in the DB with correct fields
        """
        token = _get_github_token()
        repo_name = f"justralph-e2e-test-{int(time.time())}"
        slug = repo_name.lower()
        description = "E2E test project — safe to delete"
        project_dir = os.path.join(PROJECTS_DIR, repo_name)

        db_fd, db_path = tempfile.mkstemp()
        app = _make_app(db_path)
        client = app.test_client()
        _auth_session(client, token)

        # Track what was created for cleanup
        bdui_port = None
        opencode_session_id = None

        try:
            # ----- Step 1: POST /projects/new and check redirect -----
            response = client.post(
                "/projects/new",
                data={"repo_name": repo_name, "description": description},
            )
            assert response.status_code == 302, (
                f"Step 1 FAILED: Expected redirect (302), got {response.status_code}. "
                f"Response body: {response.data.decode()[:500]}"
            )
            location = response.headers.get("Location", "")
            assert f"/projects/{slug}" in location, (
                f"Step 1 FAILED: Expected redirect to /projects/{slug}, got Location: {location}"
            )

            # ----- Read DB row for subsequent checks -----
            row = _get_project_by_slug(db_path, slug)
            assert row is not None, f"Step 7 FAILED: No project row found in DB with slug '{slug}'"
            bdui_port = row["bdui_port"]
            opencode_session_id = row["opencode_session_id"]

            # ----- Step 2: GitHub repo exists -----
            assert _github_repo_exists(repo_name, token), (
                f"Step 2 FAILED: GitHub repo {GITHUB_USERNAME}/{repo_name} does not exist"
            )

            # ----- Step 3: Local directory exists -----
            assert os.path.isdir(project_dir), f"Step 3 FAILED: Project directory does not exist at {project_dir}"

            # ----- Step 4: Beads initialized -----
            beads_dir = os.path.join(project_dir, ".beads")
            assert os.path.isdir(beads_dir), f"Step 4 FAILED: .beads/ directory does not exist in {project_dir}"

            # ----- Step 5: bdui sidecar is running -----
            assert bdui_port is not None, "Step 5 FAILED: bdui_port is NULL in the DB"
            # bdui is started via Popen (async) — give it up to 5 seconds to bind
            bdui_listening = False
            for _ in range(10):
                lsof_result = subprocess.run(
                    ["lsof", "-ti", f":{bdui_port}"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if lsof_result.stdout.strip():
                    bdui_listening = True
                    break
                time.sleep(0.5)
            assert bdui_listening, f"Step 5 FAILED: No process listening on bdui port {bdui_port} after 5s"

            # ----- Step 6: Opencode session exists -----
            assert opencode_session_id is not None, "Step 6 FAILED: opencode_session_id is NULL in the DB"
            oc_resp = requests.get(
                f"{OPENCODE_URL}/session/{opencode_session_id}",
                timeout=10,
            )
            assert oc_resp.status_code == 200, (
                f"Step 6 FAILED: GET /session/{opencode_session_id} returned {oc_resp.status_code}"
            )

            # ----- Step 7: DB row has correct fields -----
            assert row["name"] == repo_name, f"Step 7 FAILED: DB name is '{row['name']}', expected '{repo_name}'"
            assert row["slug"] == slug, f"Step 7 FAILED: DB slug is '{row['slug']}', expected '{slug}'"
            assert row["repo_url"] is not None and "github.com" in row["repo_url"], (
                f"Step 7 FAILED: DB repo_url is '{row['repo_url']}', expected a GitHub URL"
            )
            assert row["repo_url"] == f"https://github.com/{GITHUB_USERNAME}/{repo_name}", (
                f"Step 7 FAILED: DB repo_url is '{row['repo_url']}', "
                f"expected 'https://github.com/{GITHUB_USERNAME}/{repo_name}'"
            )
            assert row["description"] == description, (
                f"Step 7 FAILED: DB description is '{row['description']}', expected '{description}'"
            )
            assert row["vps_path"] == project_dir, (
                f"Step 7 FAILED: DB vps_path is '{row['vps_path']}', expected '{project_dir}'"
            )
            assert row["opencode_session_id"] == opencode_session_id, "Step 7 FAILED: DB opencode_session_id mismatch"
            assert row["bdui_port"] == bdui_port, "Step 7 FAILED: DB bdui_port mismatch"

        finally:
            # ----- Cleanup: reverse all side effects -----
            _delete_github_repo(repo_name, token)
            if os.path.isdir(project_dir):
                shutil.rmtree(project_dir, ignore_errors=True)
            _kill_process_on_port(bdui_port)
            _delete_opencode_session(opencode_session_id)
            os.close(db_fd)
            os.unlink(db_path)
