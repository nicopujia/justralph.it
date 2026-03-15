import json
import os

import markdown
import requests
from flask import Blueprint, Response, abort, current_app, redirect, render_template, request, session

from .models import get_db
from .projects import create_project, validate_repo_name
from .sse import publish, subscribe, unsubscribe

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if session.get("user"):
        return redirect("/projects")
    return render_template("index.html")


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

    data = request.get_json(force=True)
    message = data.get("message", "").strip()
    if not message:
        return {"error": "empty message"}, 400

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

    # Send the user's message
    requests.post(
        f"{opencode_url}/session/{session_id}/prompt_async",
        json={"parts": [{"type": "text", "text": message}], "agent": "RALPHY"},
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
