"""FastAPI server: session management, task CRUD, WebSocket event streaming."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import tasks

import server.db as db

from .auth import (
    create_user_session,
    exchange_code_for_token,
    get_github_auth_url,
    get_github_user,
    get_user_session,
)
from .chatbot import chat as chatbot_chat, get_chat_state
from .sessions import (
    Session,
    create_session,
    get_session,
    list_sessions,
    load_sessions_from_db,
    restart_loop,
    start_loop,
    stop_loop,
)

logger = logging.getLogger(__name__)

# -- WebSocket broadcast ------------------------------------------------------

_ws_clients: dict[str, set[WebSocket]] = {}  # session_id -> clients
_global_ws: set[WebSocket] = set()  # clients not bound to a session
_broadcast_task: asyncio.Task | None = None


async def _broadcast_events() -> None:
    """Drain all session EventBuses every 100ms, broadcast to connected clients."""
    while True:
        for session in list_sessions():
            events = session.event_bus.drain()
            if not events:
                continue

            # Session-scoped clients
            clients = _ws_clients.get(session.id, set()) | _global_ws
            if not clients:
                continue

            dead: set[WebSocket] = set()
            for event in events:
                msg = json.dumps({"session_id": session.id, **event.to_dict()})
                for ws in clients.copy():
                    try:
                        await ws.send_text(msg)
                    except Exception:
                        dead.add(ws)

            for ws in dead:
                _global_ws.discard(ws)
                _ws_clients.get(session.id, set()).discard(ws)

        await asyncio.sleep(0.1)


# -- Lifespan -----------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _broadcast_task
    db.init_db()
    load_sessions_from_db()
    _broadcast_task = asyncio.create_task(_broadcast_events())
    yield
    _broadcast_task.cancel()
    try:
        await _broadcast_task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- WebSocket ----------------------------------------------------------------


@app.websocket("/ws")
async def ws_global(ws: WebSocket):
    """Global WebSocket: receives events from ALL sessions."""
    await ws.accept()
    _global_ws.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _global_ws.discard(ws)


@app.websocket("/ws/{session_id}")
async def ws_session(ws: WebSocket, session_id: str):
    """Session-scoped WebSocket: receives events from one session only."""
    session = get_session(session_id)
    if not session:
        await ws.close(code=4004, reason="session not found")
        return
    await ws.accept()
    _ws_clients.setdefault(session_id, set()).add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.get(session_id, set()).discard(ws)


# -- Auth endpoints -----------------------------------------------------------


@app.get("/api/auth/github")
def api_auth_github():
    """Return GitHub OAuth authorize URL."""
    return {"url": get_github_auth_url()}


@app.get("/api/auth/github/callback")
async def api_auth_github_callback(code: str):
    """Exchange OAuth code for token, create session, return token + user."""
    try:
        github_token = await exchange_code_for_token(code)
        user = await get_github_user(github_token)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    session_token = create_user_session(github_token, user)
    return {"token": session_token, "user": user}


@app.get("/api/auth/me")
def api_auth_me(request: Request):
    """Return current user info from session token in Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    session_token = auth.removeprefix("Bearer ").strip()
    session = get_user_session(session_token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session token")
    return session["github_user"]


# -- Session endpoints --------------------------------------------------------


class CreateSessionRequest(BaseModel):
    github_url: str = ""
    github_token: str = ""


@app.post("/api/sessions", status_code=201)
def api_create_session(req: CreateSessionRequest):
    """Create a new isolated session with git repo + ralph scaffolding."""
    session = create_session(github_url=req.github_url, github_token=req.github_token)
    return session.to_dict()


@app.get("/api/sessions")
def api_list_sessions():
    """List all sessions."""
    return [s.to_dict() for s in list_sessions()]


@app.get("/api/sessions/{session_id}")
def api_get_session(session_id: str):
    session = _require_session(session_id)
    return session.to_dict()


@app.post("/api/sessions/{session_id}/start")
def api_start_loop(session_id: str):
    """Start the Ralph Loop for a session."""
    session = _require_session(session_id)
    try:
        start_loop(session)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"status": "started", "session_id": session_id}


@app.post("/api/sessions/{session_id}/stop")
def api_stop_loop(session_id: str):
    """Stop the running loop."""
    session = _require_session(session_id)
    try:
        stop_loop(session)
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "stop signal sent"}


@app.post("/api/sessions/{session_id}/restart")
def api_restart_loop(session_id: str):
    """Restart the running loop."""
    session = _require_session(session_id)
    try:
        restart_loop(session)
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "restart signal sent"}


@app.get("/api/sessions/{session_id}/status")
def api_session_status(session_id: str):
    session = _require_session(session_id)
    return session.to_dict()


# -- Task CRUD endpoints ------------------------------------------------------


class CreateTaskRequest(BaseModel):
    title: str
    body: str = ""
    priority: int = 2
    parent: str = ""
    labels: list[str] = []


class UpdateTaskRequest(BaseModel):
    status: str | None = None
    body: str | None = None
    priority: int | None = None
    assignee: str | None = None
    labels: list[str] | None = None
    append_notes: str | None = None


@app.post("/api/sessions/{session_id}/tasks", status_code=201)
def api_create_task(session_id: str, req: CreateTaskRequest):
    """Create a task in this session's tasks.yaml."""
    session = _require_session(session_id)
    task = tasks.create_task(
        req.title,
        body=req.body or None,
        priority=req.priority,
        labels=req.labels or None,
        parent=req.parent or None,
        cwd=session.base_dir,
    )
    return task.to_dict()


@app.get("/api/sessions/{session_id}/tasks")
def api_list_tasks(session_id: str, status: str | None = None):
    """List all tasks for a session, optionally filtered by status."""
    session = _require_session(session_id)
    task_list = tasks.list_tasks(status=status, cwd=session.base_dir)
    return [t.to_dict() for t in task_list]


@app.get("/api/sessions/{session_id}/tasks/{task_id}")
def api_get_task(session_id: str, task_id: str):
    session = _require_session(session_id)
    task = tasks.get_task(task_id, cwd=session.base_dir)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task.to_dict()


@app.patch("/api/sessions/{session_id}/tasks/{task_id}")
def api_update_task(session_id: str, task_id: str, req: UpdateTaskRequest):
    session = _require_session(session_id)
    try:
        tasks.update_task(
            task_id,
            status=req.status,
            body=req.body,
            priority=req.priority,
            assignee=req.assignee,
            labels=req.labels,
            append_notes=req.append_notes,
            cwd=session.base_dir,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "updated"}


@app.delete("/api/sessions/{session_id}/tasks/{task_id}")
def api_close_task(session_id: str, task_id: str):
    session = _require_session(session_id)
    try:
        tasks.close_task(task_id, cwd=session.base_dir)
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "closed"}


# -- File uploads (HELP flow) -------------------------------------------------


@app.post("/api/sessions/{session_id}/uploads")
async def api_upload_file(session_id: str, file: UploadFile):
    """Upload a file to the session's uploads/ directory (for HELP responses)."""
    session = _require_session(session_id)
    uploads_dir = session.base_dir / "uploads"
    uploads_dir.mkdir(exist_ok=True)
    dest = uploads_dir / (file.filename or "upload")
    content = await file.read()
    dest.write_bytes(content)
    return {"path": str(dest), "size": len(content)}


# -- Chatbot (Step 1) ---------------------------------------------------------


class ChatRequest(BaseModel):
    message: str


@app.post("/api/sessions/{session_id}/chat")
async def api_chat(session_id: str, req: ChatRequest):
    """Send a message to the Ralphy chatbot. Returns response + confidence scores.

    When confidence threshold is met, response includes generated tasks + project metadata.
    """
    session = _require_session(session_id)
    try:
        result = await chatbot_chat(session_id, req.message, session_dir=session.base_dir)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result


@app.get("/api/sessions/{session_id}/chat/state")
def api_chat_state(session_id: str):
    """Get current chatbot confidence state for a session."""
    _require_session(session_id)
    state = get_chat_state(session_id)
    return state.to_dict()


@app.get("/api/sessions/{session_id}/chat/history")
def api_chat_history(session_id: str):
    """Return persisted chat messages + state from DB."""
    _require_session(session_id)
    messages = db.load_chat_messages(session_id)
    state = db.load_chat_state(session_id)
    return {
        "messages": [{"role": m["role"], "content": m["content"], "created_at": m["created_at"]} for m in messages],
        "state": state or {},
    }


@app.post("/api/sessions/{session_id}/ralph-it")
def api_ralph_it(session_id: str):
    """'Just Ralph It' trigger: create tasks from chatbot output + start loop.

    Precondition: chatbot must be in ready state (confidence threshold met).
    """
    session = _require_session(session_id)
    chat_state = get_chat_state(session_id)

    if not chat_state.ready:
        raise HTTPException(
            status_code=400,
            detail="Chatbot confidence threshold not met yet",
        )

    if not chat_state.tasks:
        raise HTTPException(
            status_code=400,
            detail="No tasks generated by chatbot",
        )

    # Create tasks from chatbot output
    created = []
    created_ids: set[str] = set()
    for i, t in enumerate(chat_state.tasks):
        parent = t.get("parent") or ""
        # Validate parent: must reference an already-created task in this batch
        if parent and parent not in created_ids:
            logger.warning(
                "Task %d parent %r not yet created; clearing parent", i, parent
            )
            parent = ""
        task = tasks.create_task(
            t["title"],
            body=t.get("body"),
            priority=t.get("priority", i + 1),
            parent=parent,
            cwd=session.base_dir,
        )
        created.append(task.to_dict())
        created_ids.add(task.id)

    # Write project metadata to .ralphy/config.yaml if chatbot extracted it
    if chat_state.project:
        _write_project_config(session, chat_state.project)

    # Commit tasks.yaml + config to git so it's visible on GitHub
    _git_commit_session_files(session)

    # Start the loop
    try:
        start_loop(session)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {
        "status": "ralph_it_started",
        "session_id": session_id,
        "tasks_created": len(created),
        "tasks": created,
    }


def _write_project_config(session: Session, project: dict) -> None:
    """Write chatbot-extracted project metadata to .ralphy/config.yaml."""
    import yaml

    config_path = session.base_dir / ".ralphy" / "config.yaml"
    config = {
        "project": {
            "name": project.get("name", ""),
            "language": project.get("language", ""),
            "framework": project.get("framework", ""),
            "description": project.get("description", ""),
        },
        "commands": {
            "test": project.get("test_command", ""),
            "lint": project.get("lint_command", ""),
        },
        "boundaries": {"never_touch": [".ralphy/"]},
    }
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))


# -- Helpers -------------------------------------------------------------------


def _require_session(session_id: str) -> Session:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


def _git_commit_session_files(session: Session) -> None:
    """Commit tasks.yaml + .ralphy/config.yaml to git and push if remote exists."""
    import subprocess

    cwd = session.base_dir
    subprocess.run(
        ["git", "add", "tasks.yaml", ".ralphy/config.yaml"],
        cwd=cwd, capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "feat: initial tasks from Ralphy chatbot"],
        cwd=cwd, capture_output=True,
    )
    # Push if remote configured
    result = subprocess.run(
        ["git", "remote"], cwd=cwd, capture_output=True, text=True,
    )
    if "origin" in result.stdout:
        subprocess.run(
            ["git", "push", "-u", "origin", "HEAD"],
            cwd=cwd, capture_output=True,
        )
