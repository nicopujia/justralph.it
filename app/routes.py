import base64
import json
import mimetypes
import os
import sqlite3
import subprocess
import sys
import threading

import markdown
import requests
from flask import Blueprint, Response, abort, current_app, redirect, render_template, request, session

from . import PROJECT_ROOT
from .models import get_db
from .projects import create_project, validate_repo_name
from .sse import publish, subscribe, unsubscribe

bp = Blueprint("main", __name__)

ralph_processes = {}  # slug -> subprocess.Popen


@bp.route("/")
def index():
    if session.get("user"):
        return redirect("/projects")
    return render_template("index.html")


@bp.route("/projects")
def list_projects():
    if not session.get("user"):
        return redirect("/")
    db = get_db()
    projects = db.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    return render_template("projects/list.html", projects=projects)


@bp.route("/projects/new", methods=["GET"])
def new_project_form():
    if not session.get("user"):
        return redirect("/")
    return render_template("projects/new.html")


@bp.route("/projects/new", methods=["POST"])
def new_project_submit():
    if not session.get("user"):
        return redirect("/")

    repo_name = request.form.get("repo_name", "").strip()
    description = request.form.get("description", "").strip()

    # Validate repo name
    error = validate_repo_name(repo_name)
    if error:
        return render_template("projects/new.html", error=error, repo_name=repo_name, description=description), 400

    # Create the project
    token = session.get("installation_token")
    try:
        result = create_project(repo_name, description, token)
    except ValueError as e:
        return render_template("projects/new.html", error=str(e), repo_name=repo_name, description=description), 400
    except Exception as e:
        return (
            render_template(
                "projects/new.html",
                error=f"Failed to create project: {e}",
                repo_name=repo_name,
                description=description,
            ),
            500,
        )

    return redirect(f"/projects/{result['slug']}")


@bp.route("/projects/<slug>")
def show_project(slug):
    if not session.get("user"):
        return redirect("/")
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if project is None:
        abort(404)
    return render_template("projects/show.html", project=project)


@bp.route("/projects/<slug>/spec")
def project_spec(slug):
    if not session.get("user"):
        return redirect("/")
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if project is None:
        abort(404)
    vps_path = project["vps_path"]
    if vps_path is None:
        return '<p style="color: #888;">Continue chatting to let Ralphy create the spec</p>'
    agents_path = os.path.join(vps_path, "AGENTS.md")
    if not os.path.isfile(agents_path):
        return '<p style="color: #888;">Continue chatting to let Ralphy create the spec</p>'
    with open(agents_path) as f:
        content = f.read()
    return markdown.markdown(content)


@bp.route("/health")
def health():
    return {"status": "ok"}


@bp.route("/internal/projects/<slug>/show-button", methods=["POST"])
def show_button(slug):
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if project is None:
        return {"error": "not found"}, 404
    if project["ralph_running"]:
        return {"status": "no-op", "reason": "ralph_running"}
    publish(slug, "show_just_ralph_it_button", {})
    return {"status": "ok"}


@bp.route("/internal/projects/<slug>/events")
def sse_events(slug):
    def stream():
        q = subscribe(slug)
        try:
            while True:
                try:
                    event = q.get(timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                except Exception:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            unsubscribe(slug, q)

    return Response(stream(), mimetype="text/event-stream")


@bp.route("/projects/<slug>/chat/history")
def chat_history(slug):
    if not session.get("user"):
        return redirect("/")
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if project is None:
        abort(404)
    session_id = project["opencode_session_id"]
    if not session_id:
        return json.dumps([]), 200, {"Content-Type": "application/json"}
    opencode_url = current_app.config["OPENCODE_URL"]
    resp = requests.get(f"{opencode_url}/session/{session_id}/message", timeout=10)
    return resp.json(), 200


@bp.route("/projects/<slug>/chat/send", methods=["POST"])
def chat_send(slug):
    if not session.get("user"):
        return redirect("/")
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if project is None:
        abort(404)
    session_id = project["opencode_session_id"]
    if not session_id:
        return {"error": "no session"}, 400

    # Build parts from either JSON or multipart/form-data
    parts = []
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        message = request.form.get("message", "").strip()
        files = request.files.getlist("files")
        if message:
            parts.append({"type": "text", "text": message})
        for f in files:
            data = f.read()
            filename = f.filename or "upload"
            mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            b64 = base64.b64encode(data).decode()
            parts.append(
                {
                    "type": "file",
                    "mime": mime,
                    "filename": filename,
                    "url": f"data:{mime};base64,{b64}",
                }
            )
        if not parts:
            return {"error": "empty message"}, 400
    else:
        data = request.get_json(force=True)
        message = data.get("message", "").strip()
        if not message:
            return {"error": "empty message"}, 400
        parts.append({"type": "text", "text": message})

    opencode_url = current_app.config["OPENCODE_URL"]

    # If first message hasn't been sent yet, send description first
    if not project["first_message_sent"]:
        description = project["description"] or ""
        if description:
            requests.post(
                f"{opencode_url}/session/{session_id}/prompt_async",
                json={"parts": [{"type": "text", "text": description}], "agent": "RALPHY"},
                timeout=10,
            )
        db.execute("UPDATE projects SET first_message_sent = 1 WHERE slug = ?", (slug,))
        db.commit()

    # Send the user's message (text + files in one request)
    requests.post(
        f"{opencode_url}/session/{session_id}/prompt_async",
        json={"parts": parts, "agent": "RALPHY"},
        timeout=10,
    )
    return "", 204


@bp.route("/projects/<slug>/chat/events")
def chat_events(slug):
    if not session.get("user"):
        return redirect("/")
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if project is None:
        abort(404)
    session_id = project["opencode_session_id"]
    if not session_id:
        return Response("data: []\n\n", mimetype="text/event-stream")

    opencode_url = current_app.config["OPENCODE_URL"]

    def stream():
        with requests.get(f"{opencode_url}/event", stream=True, timeout=None) as resp:
            for line in resp.iter_lines():
                if not line:
                    continue
                decoded = line.decode("utf-8") if isinstance(line, bytes) else line
                if decoded.startswith("data: "):
                    try:
                        payload = json.loads(decoded[6:])
                        # Filter: only pass events for this session
                        event_session = payload.get("properties", {}).get("sessionID") or payload.get("sessionId")
                        if event_session == session_id:
                            yield f"{decoded}\n\n"
                    except (json.JSONDecodeError, KeyError):
                        # Non-JSON data lines or malformed — pass through keepalives
                        pass
                elif decoded.startswith(":"):
                    # SSE comment/keepalive
                    yield f"{decoded}\n\n"

    return Response(stream(), mimetype="text/event-stream")


@bp.route("/projects/<slug>/push/subscribe", methods=["POST"])
def push_subscribe(slug):
    if not session.get("user"):
        return redirect("/")
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if project is None:
        abort(404)
    data = request.get_json(force=True)
    subscription = data.get("subscription")
    if not subscription:
        return {"error": "missing subscription"}, 400
    sub_json = json.dumps(subscription)
    endpoint = subscription.get("endpoint", "")
    # Deduplicate: delete any existing subscription with the same endpoint for this project
    rows = db.execute(
        "SELECT id, subscription_json FROM push_subscriptions WHERE project_slug = ?",
        (slug,),
    ).fetchall()
    for row in rows:
        existing = json.loads(row["subscription_json"])
        if existing.get("endpoint") == endpoint:
            db.execute("DELETE FROM push_subscriptions WHERE id = ?", (row["id"],))
    db.execute(
        "INSERT INTO push_subscriptions (project_slug, subscription_json) VALUES (?, ?)",
        (slug, sub_json),
    )
    db.commit()
    return "", 204


@bp.route("/projects/<slug>/push/subscribe", methods=["DELETE"])
def push_unsubscribe(slug):
    if not session.get("user"):
        return redirect("/")
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if project is None:
        abort(404)
    data = request.get_json(force=True)
    endpoint = data.get("endpoint")
    if not endpoint:
        return {"error": "missing endpoint"}, 400
    rows = db.execute(
        "SELECT id, subscription_json FROM push_subscriptions WHERE project_slug = ?",
        (slug,),
    ).fetchall()
    for row in rows:
        sub = json.loads(row["subscription_json"])
        if sub.get("endpoint") == endpoint:
            db.execute("DELETE FROM push_subscriptions WHERE id = ?", (row["id"],))
    db.commit()
    return "", 204


@bp.route("/projects/<slug>/push/vapid-key")
def push_vapid_key(slug):
    if not session.get("user"):
        return redirect("/")
    return {"key": current_app.config["VAPID_APPLICATION_SERVER_KEY"]}


@bp.route("/projects/<slug>/ralph/start", methods=["POST"])
def ralph_start(slug):
    if not session.get("user"):
        return redirect("/")
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if project is None:
        abort(404)
    if project["ralph_running"] == 1:
        return {"error": "ralph already running"}, 409

    db.execute("UPDATE projects SET ralph_running = 1 WHERE slug = ?", (slug,))
    db.commit()

    ralph_py_path = os.path.join(PROJECT_ROOT, "ralph.py")
    process = subprocess.Popen(
        [sys.executable, ralph_py_path],
        cwd=project["vps_path"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    ralph_processes[slug] = process

    publish(slug, "ralph_started", {})

    db_path = current_app.config["DATABASE"]
    vapid_private_key_path = current_app.config["VAPID_PRIVATE_KEY_PATH"]
    vapid_claims_email = current_app.config["VAPID_CLAIMS_EMAIL"]

    def _watch_ralph():
        # Drain stdout and capture the last non-empty line to detect exit reason
        last_line = ""
        if process.stdout:
            for raw_line in process.stdout:
                decoded = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
                stripped = decoded.strip()
                if stripped:
                    last_line = stripped
        rc = process.wait()
        # Only clean up if wait() returned a real exit code (int)
        if not isinstance(rc, int):
            return
        # Only clean up if this process is still the active one for this slug
        if ralph_processes.get(slug) is not process:
            return
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("UPDATE projects SET ralph_running = 0 WHERE slug = ?", (slug,))
            conn.commit()
            conn.close()
        except Exception:
            pass
        # Determine exit reason from last stdout line
        reason = "all_done" if last_line == "NO MORE ISSUES LEFT" else "human_needed"
        publish(slug, "ralph_stopped", {"reason": reason})
        from .push import send_push_notification

        push_message = (
            "Ralph is done building your project." if reason == "all_done" else "Ralph is blocked and needs your help."
        )
        send_push_notification(slug, push_message, db_path, vapid_private_key_path, vapid_claims_email)
        ralph_processes.pop(slug, None)

    t = threading.Thread(target=_watch_ralph, daemon=True)
    t.start()

    return {"status": "started"}, 200


@bp.route("/projects/<slug>/ralph/output")
def ralph_output(slug):
    if not session.get("user"):
        return redirect("/")
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if project is None:
        abort(404)

    def stream():
        proc = ralph_processes.get(slug)
        if proc and proc.stdout:
            for line in proc.stdout:
                decoded = line.decode("utf-8", errors="replace").rstrip("\n")
                yield f"data: {decoded}\n\n"
        yield "data: [DONE]\n\n"

    return Response(stream(), mimetype="text/event-stream")
