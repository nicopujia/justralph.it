import json

from flask import Blueprint, Response, redirect, render_template, request, session

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
