import base64
import json
import mimetypes
import os
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import markdown
import requests
import websocket as websocket_client
from flask import Blueprint, Response, abort, current_app, redirect, render_template, request, session

from . import PROJECT_ROOT, sock
from .models import get_db
from .projects import (
    create_project,
    delete_github_repo,
    delete_opencode_session,
    remove_vps_directory,
    stop_bdui,
    validate_repo_name,
)
from .sse import publish, subscribe, unsubscribe
from .subprocess_env import subprocess_env

bp = Blueprint("main", __name__)

ralph_processes = {}  # slug -> subprocess.Popen
ralph_output_buffers = {}  # slug -> {"lines": list, "done": threading.Event}
STOP_FILE = Path.home() / "projects" / "just-ralph-it" / ".stop"

# Read-only WebSocket message types allowed through the bdui proxy
ALLOWED_WS_TYPES = {"subscribe-list", "unsubscribe-list", "pong"}


@bp.route("/")
def index():
    if session.get("user"):
        return redirect("/projects")
    return render_template("index.html")


@bp.route("/prd")
def prd():
    return redirect("https://nicolaspujia.com/ralph")


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
    token = session.get("github_token")
    try:
        result = create_project(repo_name, description, token, session.get("user"))
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


@bp.route("/projects/<slug>/delete", methods=["POST"])
def delete_project(slug):
    if not session.get("user"):
        return redirect("/")
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if project is None:
        abort(404)

    token = session.get("github_token")

    # Kill ralph process if running
    proc = ralph_processes.pop(slug, None)
    if proc:
        try:
            proc.kill()
        except Exception:
            pass

    # Best-effort cleanup: GitHub repo (only if user opted in), bdui, opencode session, VPS directory
    if request.form.get("delete_github_repo"):
        try:
            delete_github_repo(project["name"], token, session.get("user"))
        except Exception:
            pass
    try:
        stop_bdui(project["bdui_port"])
    except Exception:
        pass
    try:
        delete_opencode_session(project["opencode_session_id"])
    except Exception:
        pass
    try:
        remove_vps_directory(project["vps_path"])
    except Exception:
        pass

    # Remove push subscriptions and project from DB
    db.execute("DELETE FROM push_subscriptions WHERE project_slug = ?", (slug,))
    db.execute("DELETE FROM projects WHERE slug = ?", (slug,))
    db.commit()

    return redirect("/projects")


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
                    event = q.get(timeout=15)
                    yield f"data: {json.dumps(event)}\n\n"
                except Exception:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            unsubscribe(slug, q)

    resp = Response(stream(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


@bp.route("/projects/<slug>/chat/init", methods=["POST"])
def chat_init(slug):
    """Auto-send the project description as the first message to Ralphy.

    Called by the frontend on page load when first_message_sent=0.
    This ensures Ralphy gets the description immediately after project creation
    without waiting for the user to type something.
    """
    if not session.get("user"):
        return redirect("/")
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if project is None:
        abort(404)
    session_id = project["opencode_session_id"]
    if not session_id:
        return {"error": "no session"}, 400
    if project["first_message_sent"]:
        return {"status": "already_sent"}, 200

    description = project["description"] or ""
    opencode_url = current_app.config["OPENCODE_URL"]
    if description:
        requests.post(
            f"{opencode_url}/session/{session_id}/prompt_async",
            json={"parts": [{"type": "text", "text": description}], "agent": "RALPHY"},
            timeout=10,
        )
    db.execute("UPDATE projects SET first_message_sent = 1 WHERE slug = ?", (slug,))
    db.commit()
    return {"status": "sent"}, 200


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
        try:
            with requests.get(f"{opencode_url}/event", stream=True, timeout=(5, 30)) as resp:
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
        except GeneratorExit:
            return
        except Exception:
            # Upstream timed out or connection lost — send keepalive comment and let client reconnect
            yield ": keepalive\n\n"

    resp = Response(stream(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


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
    env = subprocess_env(PYTHONUNBUFFERED="1")
    process = subprocess.Popen(
        [sys.executable, ralph_py_path],
        cwd=project["vps_path"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    ralph_output_buffers[slug] = {"lines": [], "done": threading.Event()}
    ralph_processes[slug] = process

    publish(slug, "ralph_started", {})

    db_path = current_app.config["DATABASE"]
    vapid_private_key_path = current_app.config["VAPID_PRIVATE_KEY_PATH"]
    vapid_claims_email = current_app.config["VAPID_CLAIMS_EMAIL"]

    def _watch_ralph():
        # Drain stdout and capture the last two non-empty lines to detect exit reason
        prev_line = ""
        last_line = ""
        buf = ralph_output_buffers.get(slug)
        if process.stdout:
            for raw_line in process.stdout:
                decoded = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
                stripped = decoded.strip()
                if buf is not None:
                    buf["lines"].append(decoded.rstrip("\n"))
                if stripped:
                    prev_line = last_line
                    last_line = stripped
        if buf is not None:
            buf["done"].set()
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
        if last_line == "NO MORE ISSUES LEFT":
            reason = "all_done"
        elif last_line == "STOPPING AS REQUESTED":
            reason = "stopped"
        elif last_line == "STOPPING: VPS RESOURCES EXCEEDED":
            reason = "resources_exhausted"
        else:
            reason = "human_needed"
        publish(slug, "ralph_stopped", {"reason": reason})
        from .push import send_push_notification

        if reason == "all_done":
            push_message = "Ralph is done building your project."
        elif reason == "stopped":
            push_message = "Ralph was stopped. Click Continue to resume."
        elif reason == "resources_exhausted":
            push_message = (
                prev_line
                if prev_line.startswith("Ralph stopped: VPS resources")
                else "Ralph stopped: VPS resources critically low. Free up space or upgrade before continuing."
            )
        else:
            push_message = "Ralph is blocked and needs your help."
        send_push_notification(slug, push_message, db_path, vapid_private_key_path, vapid_claims_email)
        ralph_processes.pop(slug, None)
        ralph_output_buffers.pop(slug, None)

    t = threading.Thread(target=_watch_ralph, daemon=True)
    t.start()

    return {"status": "started"}, 200


@bp.route("/projects/<slug>/ralph/stop", methods=["POST"])
def ralph_stop(slug):
    if not session.get("user"):
        return redirect("/")
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if project is None:
        abort(404)
    if project["ralph_running"] != 1:
        return {"error": "ralph not running"}, 409

    STOP_FILE.touch()
    publish(slug, "ralph_stopping", {})

    return {"status": "stopping"}, 200


@bp.route("/projects/<slug>/ralph/force-stop", methods=["POST"])
def ralph_force_stop(slug):
    if not session.get("user"):
        return redirect("/")
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if project is None:
        abort(404)
    if project["ralph_running"] != 1:
        return {"error": "ralph not running"}, 409

    proc = ralph_processes.pop(slug, None)
    if proc:
        proc.kill()

    subprocess.run(
        "git reset --hard origin/main && git clean -fd",
        shell=True,
        cwd=project["vps_path"],
    )

    db.execute("UPDATE projects SET ralph_running = 0 WHERE slug = ?", (slug,))
    db.commit()

    publish(slug, "ralph_stopped", {"reason": "force_stopped", "message": "Force stopped and reset to origin"})

    return {"status": "force_stopped"}, 200


@bp.route("/projects/<slug>/ralph/output")
def ralph_output(slug):
    if not session.get("user"):
        return redirect("/")
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if project is None:
        abort(404)

    def stream():
        buf = ralph_output_buffers.get(slug)
        if not buf:
            yield "data: [DONE]\n\n"
            return
        idx = 0
        try:
            while True:
                while idx < len(buf["lines"]):
                    yield f"data: {buf['lines'][idx]}\n\n"
                    idx += 1
                if buf["done"].is_set():
                    # Drain any remaining lines added between check and set
                    while idx < len(buf["lines"]):
                        yield f"data: {buf['lines'][idx]}\n\n"
                        idx += 1
                    break
                time.sleep(0.2)
        except GeneratorExit:
            return
        yield "data: [DONE]\n\n"

    resp = Response(stream(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


@sock.route("/projects/<slug>/bdui/ws")
def bdui_ws_proxy(ws, slug):
    """WebSocket proxy to bdui — only forwards read-only messages from client to bdui."""
    if not session.get("user"):
        ws.close(reason="unauthorized")
        return

    db = get_db()
    project = db.execute("SELECT bdui_port FROM projects WHERE slug = ?", (slug,)).fetchone()
    if not project or not project["bdui_port"]:
        ws.close(reason="not found")
        return

    port = project["bdui_port"]

    backend_ws = websocket_client.WebSocket()
    backend_ws.connect(f"ws://127.0.0.1:{port}/ws")

    closed = threading.Event()

    def forward_from_backend():
        try:
            while not closed.is_set():
                data = backend_ws.recv()
                if data:
                    ws.send(data)
        except Exception:
            closed.set()

    t = threading.Thread(target=forward_from_backend, daemon=True)
    t.start()

    try:
        while not closed.is_set():
            data = ws.receive(timeout=30)
            if data is None:
                break
            # Filter: only allow read-only message types
            try:
                msg = json.loads(data)
                if msg.get("type") in ALLOWED_WS_TYPES:
                    backend_ws.send(data)
            except (json.JSONDecodeError, KeyError):
                pass  # Drop malformed messages
    except Exception:
        pass
    finally:
        closed.set()
        try:
            backend_ws.close()
        except Exception:
            pass
