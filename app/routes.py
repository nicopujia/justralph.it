import json

from flask import Blueprint, Response, render_template

from .models import get_db
from .sse import publish, subscribe, unsubscribe

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


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
