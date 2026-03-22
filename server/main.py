"""FastAPI server: session management, task CRUD, WebSocket event streaming."""

import asyncio
import json
import logging
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal

import tasks

import server.db as db

from .auth import (
    create_user_session,
    exchange_code_for_token,
    get_github_auth_url,
    get_github_user,
    get_user_session,
)
from .chatbot import DIMENSIONS, TOOL_CONFIGS, ChatState, _chat_states, chat as chatbot_chat, get_chat_state, reconcile_tasks, run_tool as chatbot_run_tool, undo_last_message
from .sessions import (
    Session,
    create_session,
    delete_session,
    force_stop_loop,
    get_session,
    kill_current_task,
    list_sessions,
    load_sessions_from_db,
    rename_session,
    restart_loop,
    start_loop,
    stop_loop,
)

logger = logging.getLogger(__name__)

# -- WebSocket broadcast ------------------------------------------------------

_ws_clients: dict[str, set[WebSocket]] = {}  # session_id -> clients
_global_ws: set[WebSocket] = set()  # clients not bound to a session
_broadcast_task: asyncio.Task | None = None

# Per-session ring buffer of last 50 serialized events for replay on reconnect.
_EVENT_REPLAY_MAX = 50
_event_replay_buffer: dict[str, list[str]] = {}  # session_id -> list[json_str]


async def _broadcast_events() -> None:
    """Drain all session EventBuses every 100ms, broadcast to connected clients."""
    while True:
        for session in list_sessions():
            events = session.event_bus.drain()
            if not events:
                continue

            # Serialize and buffer events for replay
            serialized: list[str] = []
            for event in events:
                msg = json.dumps({"session_id": session.id, **event.to_dict()})
                serialized.append(msg)

            buf = _event_replay_buffer.setdefault(session.id, [])
            buf.extend(serialized)
            if len(buf) > _EVENT_REPLAY_MAX:
                del buf[: len(buf) - _EVENT_REPLAY_MAX]

            # Session-scoped clients
            clients = _ws_clients.get(session.id, set()) | _global_ws
            if not clients:
                continue

            dead: set[WebSocket] = set()
            for msg in serialized:
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
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        _global_ws.discard(ws)


@app.websocket("/ws/{session_id}")
async def ws_session(ws: WebSocket, session_id: str):
    """Session-scoped WebSocket: receives events from one session only.

    Replays the last 50 buffered events on connect so clients don't miss events
    during disconnection.
    """
    session = get_session(session_id)
    if not session:
        await ws.close(code=4004, reason="session not found")
        return
    await ws.accept()
    _ws_clients.setdefault(session_id, set()).add(ws)
    # Replay buffered events so reconnecting clients catch up.
    for msg in _event_replay_buffer.get(session_id, []):
        try:
            await ws.send_text(msg)
        except Exception:
            break
    try:
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text("pong")
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


class PatchSessionRequest(BaseModel):
    name: str


@app.patch("/api/sessions/{session_id}")
def api_patch_session(session_id: str, req: PatchSessionRequest):
    """Update session metadata (currently: name only)."""
    session = _require_session(session_id)
    rename_session(session, req.name.strip())
    return session.to_dict()


@app.post("/api/sessions/{session_id}/start")
def api_start_loop(session_id: str):
    """Start the Ralph Loop for a session.

    Contextually aware: auto-recovers dead threads, allows restart from
    crashed/stopped state.
    """
    session = _require_session(session_id)

    # Auto-recover: thread is dead but status still says "running"
    if session.thread and not session.thread.is_alive():
        session.thread = None
        session.runner = None
        if session.status == "running":
            session.status = "crashed"
            db.update_session_status(session.id, "crashed")

    try:
        start_loop(session)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail={
            "error": str(e),
            "current_status": session.status,
            "suggestion": "Stop the running loop first, or use force=true on the stop endpoint.",
        })
    return {"status": "started", "session_id": session_id}


@app.post("/api/sessions/{session_id}/stop")
def api_stop_loop(session_id: str, force: bool = False):
    """Stop the running loop. Use ?force=true to kill subprocess immediately."""
    session = _require_session(session_id)

    if force:
        try:
            force_stop_loop(session)
        except RuntimeError as e:
            raise HTTPException(status_code=400, detail={
                "error": str(e),
                "current_status": session.status,
                "suggestion": "The loop may have already stopped.",
            })
        return {"status": "force_stopped", "session_id": session_id}

    try:
        stop_loop(session)
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail={
            "error": str(e),
            "current_status": session.status,
            "suggestion": "No loop is currently running. Use /start to begin.",
        })
    return {"status": "stop signal sent"}


@app.post("/api/sessions/{session_id}/restart")
def api_restart_loop(session_id: str):
    """Restart the running loop."""
    session = _require_session(session_id)
    try:
        restart_loop(session)
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail={
            "error": str(e),
            "current_status": session.status,
            "suggestion": "No loop is running. Use /start instead.",
        })
    return {"status": "restart signal sent"}


@app.post("/api/sessions/{session_id}/kill-task")
def api_kill_task(session_id: str):
    """Kill the current agent subprocess and skip to next task.

    The loop continues running -- only the current task is killed and marked BLOCKED.
    """
    session = _require_session(session_id)
    try:
        task_id = kill_current_task(session)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail={
            "error": str(e),
            "current_status": session.status,
            "suggestion": "No task is currently being processed.",
        })
    return {"status": "task_killed", "task_id": task_id}


@app.get("/api/sessions/{session_id}/status")
def api_session_status(session_id: str):
    session = _require_session(session_id)
    return session.to_dict()


@app.get("/api/sessions/{session_id}/loop/state")
def api_loop_state(session_id: str):
    """Detailed loop observability: state, current task, heartbeat, thread liveness."""
    session = _require_session(session_id)
    thread_alive = session.thread is not None and session.thread.is_alive()
    elapsed: float | None = None
    if thread_alive and session.loop_start_time:
        elapsed = round(time.time() - session.loop_start_time, 2)
    return {
        "loop_state": session.loop_state,
        "current_task_id": session.current_task_id,
        "loop_elapsed_seconds": elapsed,
        "last_heartbeat_at": session.last_heartbeat_at,
        "thread_alive": thread_alive,
    }


@app.get("/api/sessions/{session_id}/git/status")
def api_git_status(session_id: str):
    """Git repository status: remote URL, branch, last push, unpushed commits."""
    import subprocess as sp

    session = _require_session(session_id)
    cwd = session.base_dir

    # Remote URL
    remote_url = ""
    try:
        r = sp.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, cwd=cwd)
        if r.returncode == 0:
            remote_url = r.stdout.strip()
    except Exception:
        pass

    # Current branch
    branch = ""
    try:
        r = sp.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, cwd=cwd)
        if r.returncode == 0:
            branch = r.stdout.strip()
    except Exception:
        pass

    # Unpushed commit count
    unpushed = 0
    if remote_url:
        try:
            r = sp.run(
                ["git", "rev-list", "--count", f"origin/{branch}..HEAD"],
                capture_output=True, text=True, cwd=cwd,
            )
            if r.returncode == 0:
                unpushed = int(r.stdout.strip())
        except Exception:
            pass

    # Last commit SHA + message
    last_commit = None
    try:
        r = sp.run(
            ["git", "log", "-1", "--format=%H|%s|%aI"],
            capture_output=True, text=True, cwd=cwd,
        )
        if r.returncode == 0 and r.stdout.strip():
            parts = r.stdout.strip().split("|", 2)
            if len(parts) == 3:
                last_commit = {"sha": parts[0][:8], "message": parts[1], "date": parts[2]}
    except Exception:
        pass

    return {
        "remote_url": remote_url,
        "branch": branch,
        "unpushed_commits": unpushed,
        "last_commit": last_commit,
        "has_remote": bool(remote_url),
    }


@app.get("/api/sessions/{session_id}/tasks/{task_id}/diff")
def api_task_diff(session_id: str, task_id: str):
    """Get the git diff for a specific completed task."""
    import subprocess as sp

    session = _require_session(session_id)
    cwd = session.base_dir

    # Find the commit for this task by searching commit messages
    try:
        r = sp.run(
            ["git", "log", "--all", "--oneline", "--grep", task_id],
            capture_output=True, text=True, cwd=cwd,
        )
        if r.returncode != 0 or not r.stdout.strip():
            raise HTTPException(status_code=404, detail=f"No commit found for task {task_id}")

        # Take the first (most recent) match
        commit_sha = r.stdout.strip().split("\n")[0].split()[0]

        # Get the diff for that commit
        diff_result = sp.run(
            ["git", "diff", f"{commit_sha}~1", commit_sha],
            capture_output=True, text=True, cwd=cwd,
        )
        diff_text = diff_result.stdout.strip() if diff_result.returncode == 0 else ""

        return {"task_id": task_id, "commit": commit_sha, "diff": diff_text}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get diff: {e}")


@app.get("/api/sessions/{session_id}/diff")
def api_cumulative_diff(session_id: str):
    """Get the cumulative diff (all changes from initial commit to HEAD)."""
    import subprocess as sp

    session = _require_session(session_id)
    cwd = session.base_dir

    try:
        # Get the first commit (root)
        r = sp.run(
            ["git", "rev-list", "--max-parents=0", "HEAD"],
            capture_output=True, text=True, cwd=cwd,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return {"diff": "", "commit_count": 0}

        root_sha = r.stdout.strip().split("\n")[0]

        # Count commits
        count_r = sp.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, cwd=cwd,
        )
        commit_count = int(count_r.stdout.strip()) if count_r.returncode == 0 else 0

        # Get cumulative diff
        diff_r = sp.run(
            ["git", "diff", root_sha, "HEAD"],
            capture_output=True, text=True, cwd=cwd,
        )
        diff_text = diff_r.stdout.strip() if diff_r.returncode == 0 else ""

        return {"diff": diff_text, "commit_count": commit_count}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get diff: {e}")


@app.delete("/api/sessions/{session_id}")
def api_delete_session(session_id: str):
    """Stop loop if running, delete session dir, DB rows, and in-memory state."""
    session = _require_session(session_id)
    delete_session(session)
    _chat_states.pop(session_id, None)
    _ws_clients.pop(session_id, None)
    _event_replay_buffer.pop(session_id, None)
    return {"status": "deleted", "session_id": session_id}


@app.post("/api/sessions/{session_id}/duplicate", status_code=201)
def api_duplicate_session(session_id: str):
    """Create a new session with the same chat history as the source."""
    source = _require_session(session_id)
    new_session = create_session()
    messages = db.load_chat_messages(session_id)
    for m in messages:
        db.save_chat_message(new_session.id, m["role"], m["content"])
    source_state = db.load_chat_state(session_id)
    if source_state:
        db.save_chat_state(
            new_session.id,
            confidence=source_state.get("confidence", {}),
            relevance=source_state.get("relevance", {}),
            ready=source_state.get("ready", False),
            weighted_readiness=source_state.get("weighted_readiness", 0),
            tasks=source_state.get("tasks"),
            project=source_state.get("project"),
        )
    rename_session(new_session, f"Copy of {source.name or source.id[:8]}")
    return new_session.to_dict()


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
    if session.event_bus:
        from pkgs.ralph.core.events import Event, EventType
        session.event_bus.emit(Event(type=EventType.TASK_CREATED, data={
            "task_id": task.id, "title": task.title, "status": str(task.status),
            "priority": task.priority, "body": task.body,
        }))
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
    if session.event_bus:
        from pkgs.ralph.core.events import Event, EventType
        session.event_bus.emit(Event(type=EventType.TASK_UPDATED, data={
            "task_id": task_id,
            "status": req.status, "body": req.body, "priority": req.priority,
        }))
    return {"status": "updated"}


@app.delete("/api/sessions/{session_id}/tasks/{task_id}")
def api_delete_task(session_id: str, task_id: str):
    """Delete a task entirely from tasks.yaml. Refuses to delete IN_PROGRESS tasks."""
    session = _require_session(session_id)
    try:
        tasks.delete_task(task_id, cwd=session.base_dir)
    except RuntimeError as e:
        code = 400 if "in progress" in str(e).lower() else 404
        raise HTTPException(status_code=code, detail=str(e))
    # Emit event so frontend updates in real-time
    if session.event_bus:
        from pkgs.ralph.core.events import Event, EventType
        session.event_bus.emit(Event(type=EventType.TASK_DELETED, data={"task_id": task_id}))
    return {"status": "deleted", "task_id": task_id}


class ReorderRequest(BaseModel):
    task_ids: list[str]


@app.post("/api/sessions/{session_id}/tasks/reorder")
def api_reorder_tasks(session_id: str, req: ReorderRequest):
    """Reassign task priorities based on array order (index 0 = priority 1)."""
    session = _require_session(session_id)
    try:
        tasks.reorder_tasks(req.task_ids, cwd=session.base_dir)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "reordered", "count": len(req.task_ids)}


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
    """Return persisted chat messages + state from DB.

    Assistant messages are stored as JSON strings internally.
    This endpoint parses them and returns the human-readable `.message`
    as `content`, with the full parsed object in `metadata`.
    State fields are flattened to the top level for easy frontend consumption.
    """
    _require_session(session_id)
    messages = db.load_chat_messages(session_id)
    state = db.load_chat_state(session_id)

    parsed_messages = []
    for m in messages:
        entry: dict = {"role": m["role"], "content": m["content"], "created_at": m["created_at"]}
        if m["role"] == "assistant":
            try:
                parsed = json.loads(m["content"])
                entry["content"] = parsed.get("message", m["content"])
                entry["metadata"] = parsed
            except (json.JSONDecodeError, TypeError):
                pass
        parsed_messages.append(entry)

    # Flatten state to top level so frontend can read confidence, readiness, etc. directly
    flat: dict = {"messages": parsed_messages}
    if state:
        flat["confidence"] = state.get("confidence", {})
        flat["relevance"] = state.get("relevance", {})
        flat["ready"] = state.get("ready", False)
        flat["weighted_readiness"] = state.get("weighted_readiness", 0)
        flat["tasks"] = state.get("tasks")
        flat["project"] = state.get("project")
    flat["state"] = state or {}
    return flat


@app.get("/api/sessions/{session_id}/chat/summary")
def api_chat_summary(session_id: str):
    """Structured summary of chat state: project info, dimension scores, readiness."""
    _require_session(session_id)
    chat_state = get_chat_state(session_id)

    dim_labels = {
        "functional": "Functional requirements",
        "technical_stack": "Technical stack",
        "data_model": "Data model",
        "auth": "Auth & roles",
        "deployment": "Deployment",
        "testing": "Testing strategy",
        "edge_cases": "Edge cases",
    }

    dimensions = {}
    for d in DIMENSIONS:
        score = chat_state.confidence.get(d, 0)
        if score > 0:
            dimensions[d] = {"score": score, "label": dim_labels.get(d, d)}

    return {
        "project": chat_state.project,
        "dimensions": dimensions,
        "question_count": chat_state.user_msg_count,
        "ready": chat_state.ready,
    }


@app.post("/api/sessions/{session_id}/chat/clear")
def api_chat_clear(session_id: str):
    """Delete all chat messages for a session and reset in-memory chatbot state."""
    _require_session(session_id)
    db.delete_chat_messages(session_id)
    # Reset in-memory state but keep the session alive
    _chat_states[session_id] = ChatState()
    return {"status": "cleared"}


@app.post("/api/sessions/{session_id}/chat/undo")
def api_chat_undo(session_id: str):
    """Undo last user+assistant message pair, recalculate confidence from history."""
    _require_session(session_id)
    try:
        result = undo_last_message(session_id)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


class ToolRequest(BaseModel):
    tool: Literal["brainstorm", "expand", "refine", "architect", "modify"]
    context: str = ""  # optional freeform input (for refine tool)


@app.post("/api/sessions/{session_id}/chat/tool")
async def api_run_tool(session_id: str, req: ToolRequest):
    """Run a chatbot tool (brainstorm, expand, refine, architect)."""
    session = _require_session(session_id)
    try:
        result = await chatbot_run_tool(
            session_id, req.tool, req.context, session_dir=session.base_dir
        )
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@app.get("/api/sessions/{session_id}/chat/tools")
def api_chat_tools(session_id: str):
    """Return tool gating state for the session."""
    _require_session(session_id)
    state = get_chat_state(session_id)

    tools = {}
    for tool_id, config in TOOL_CONFIGS.items():
        enabled = config["gate"](state)
        tools[tool_id] = {
            "enabled": enabled,
            "reason": None if enabled else config["gate_reason"],
            "mode": config["mode"],
        }
    return {"tools": tools}


class RalphItRequest(BaseModel):
    # Optional override: user-edited tasks from the preview step.
    # If omitted, the server uses chatbot-generated tasks.
    tasks: list[dict] | None = None


@app.post("/api/sessions/{session_id}/reconcile")
def api_reconcile(session_id: str):
    """Run the reconciliation agent on current conversation + tasks.

    Returns reconciled task list for user review in TaskPreview.
    Does NOT start the loop -- that still requires POST /ralph-it.
    """
    _require_session(session_id)
    chat_state = get_chat_state(session_id)

    if not chat_state.ready:
        raise HTTPException(
            status_code=400,
            detail="Chatbot confidence threshold not met yet",
        )

    if not chat_state.tasks:
        raise HTTPException(
            status_code=400,
            detail="No tasks extracted from conversation yet",
        )

    session = _require_session(session_id)
    result = reconcile_tasks(session_id, session_dir=session.base_dir)

    if not result:
        return {
            "tasks": chat_state.tasks,
            "project": chat_state.project,
            "changes_summary": "Reconciliation unavailable -- returning original tasks",
            "reconciled": False,
        }

    return {
        "tasks": result["tasks"],
        "project": result.get("project", chat_state.project),
        "changes_summary": result.get("changes_summary", ""),
        "reconciled": True,
    }


@app.post("/api/sessions/{session_id}/ralph-it")
def api_ralph_it(session_id: str, req: RalphItRequest = RalphItRequest()):
    """'Just Ralph It' trigger: create tasks from chatbot output + start loop.

    Precondition: chatbot must be in ready state (confidence threshold met).
    Accepts optional body `{ "tasks": [...] }` to use user-edited tasks instead.
    """
    session = _require_session(session_id)
    chat_state = get_chat_state(session_id)

    if not chat_state.ready:
        raise HTTPException(
            status_code=400,
            detail="Chatbot confidence threshold not met yet",
        )

    # Guard: reject if tasks already exist for this session (double-click protection)
    existing = tasks.list_tasks(cwd=session.base_dir)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Tasks already exist for this session ({len(existing)} tasks). Delete them first to re-create.",
        )

    # Use override if provided, else fall back to chatbot-generated tasks
    task_list = req.tasks if req.tasks is not None else chat_state.tasks

    if not task_list:
        raise HTTPException(
            status_code=400,
            detail="No tasks generated by chatbot",
        )

    # Validate task quality before committing to the loop
    warnings: list[str] = []
    for i, t in enumerate(task_list):
        title = t.get("title", "")
        if not title:
            raise HTTPException(status_code=400, detail=f"Task {i} has no title")
        # Check for structured acceptance criteria (new format)
        ac = t.get("acceptance_criteria")
        body = t.get("body", "")
        if ac and isinstance(ac, list):
            if len(ac) < 2:
                warnings.append(f"Task '{title}': only {len(ac)} acceptance criteria (recommend 2+)")
        elif body:
            # Legacy format: count bullet points in body
            bullets = [ln for ln in body.splitlines() if ln.strip().startswith("- ")]
            if len(bullets) < 2:
                warnings.append(f"Task '{title}': fewer than 2 acceptance criteria in body")
        else:
            warnings.append(f"Task '{title}': no acceptance criteria or body")
    if warnings:
        logger.warning("Task quality warnings: %s", warnings)

    # Create tasks from the resolved list
    created = []
    created_ids: set[str] = set()
    for i, t in enumerate(task_list):
        parent = t.get("parent") or ""
        # Validate parent: must reference an already-created task in this batch
        if parent and parent not in created_ids:
            logger.warning(
                "Task %d parent %r not yet created; clearing parent", i, parent
            )
            parent = ""

        # Normalize structured format -> body string (backwards compat with task store)
        body = t.get("body", "")
        acceptance = t.get("acceptance_criteria")
        design = t.get("design_notes")
        if acceptance and isinstance(acceptance, list):
            body = "Acceptance:\n" + "\n".join(f"- {c}" for c in acceptance)
            if design and isinstance(design, list):
                body += "\n\nDesign:\n" + "\n".join(f"- {n}" for n in design)

        # Map complexity to labels for downstream timeout scaling
        complexity = t.get("estimated_complexity", "medium")
        labels = [f"complexity:{complexity}"] if complexity else []

        task = tasks.create_task(
            t["title"],
            body=body or None,
            priority=t.get("priority", i + 1),
            parent=parent,
            labels=labels or None,
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


# -- Session sharing -----------------------------------------------------------


@app.post("/api/sessions/{session_id}/share")
def api_share_session(session_id: str, request: Request):
    """Generate (or return existing) a share token for a session.

    Returns the shareable URL so the caller can copy it to clipboard.
    """
    session = _require_session(session_id)
    if not session.share_token:
        token = secrets.token_urlsafe(16)
        session.share_token = token
        db.set_share_token(session_id, token)
    base = str(request.base_url).rstrip("/")
    return {"share_token": session.share_token, "url": f"{base}/shared/{session.share_token}"}


@app.get("/api/shared/{share_token}")
def api_get_shared(share_token: str):
    """Public read-only view of a shared session (no auth required).

    Returns session metadata + chat history.
    """
    row = db.get_session_by_share_token(share_token)
    if not row:
        raise HTTPException(status_code=404, detail="Shared session not found")
    session_id = row["id"]
    messages = db.load_chat_messages(session_id)
    state = db.load_chat_state(session_id)

    parsed_messages = []
    for m in messages:
        entry: dict = {"role": m["role"], "content": m["content"], "created_at": m["created_at"]}
        if m["role"] == "assistant":
            try:
                parsed = json.loads(m["content"])
                entry["content"] = parsed.get("message", m["content"])
                entry["metadata"] = parsed
            except (json.JSONDecodeError, TypeError):
                pass
        parsed_messages.append(entry)

    return {
        "session": {
            "id": session_id,
            "name": row.get("name", ""),
            "github_url": row.get("github_url", ""),
            "status": row.get("status", ""),
            "created_at": row.get("created_at"),
        },
        "messages": parsed_messages,
        "state": state or {},
    }


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
