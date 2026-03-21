"""FastAPI server bridging Ralph Loop to the React UI.

Endpoints:
    GET  /                        Health check
    GET  /api/issues              List all bd issues
    GET  /api/issues/{issue_id}   Get a single issue
    POST /api/sessions/start      Init + start Ralph Loop in background
    POST /api/sessions/stop       Graceful stop via signal file
    WS   /ws                      Stream lifecycle events to browser
"""

import asyncio
import logging
import threading
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

import bd
from ralph.cmds.loop import Loop, LoopConfig
from ralph.cmds.init import Init, InitConfig
from ralph.config import PROD_WORKTREE, RALPH_DIR_NAME
from ralph.core.events import Event, EventBus, EventType

logger = logging.getLogger(__name__)

app = FastAPI(title="justralph.it")
bus = EventBus()

# Track the running loop thread (single-user, single-session for demo)
_loop_thread: threading.Thread | None = None


# -- models ----------------------------------------------------------------


class StartRequest(BaseModel):
    base_dir: str
    model: str = "openrouter/anthropic/claude-sonnet-4.6"
    remote: str = ""


class StopRequest(BaseModel):
    base_dir: str


# -- health ----------------------------------------------------------------


@app.get("/")
def health():
    return {"status": "ok"}


# -- issues ----------------------------------------------------------------


@app.get("/api/issues")
def list_issues(base_dir: str = ""):
    cwd = Path(base_dir) if base_dir else None
    issues = bd.list_issues(cwd=cwd)
    return [asdict(i) for i in issues]


@app.get("/api/issues/{issue_id}")
def get_issue(issue_id: str, base_dir: str = ""):
    cwd = Path(base_dir) if base_dir else None
    issue = bd.get_issue(issue_id, cwd=cwd)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return asdict(issue)


# -- session control -------------------------------------------------------


@app.post("/api/sessions/start")
def start_session(req: StartRequest):
    global _loop_thread

    if _loop_thread is not None and _loop_thread.is_alive():
        raise HTTPException(status_code=409, detail="A session is already running")

    base = Path(req.base_dir)

    # Init if not already initialized
    ralph_dir = base / PROD_WORKTREE / RALPH_DIR_NAME
    if not ralph_dir.is_dir():
        init_cmd = Init()
        init_cmd.cfg = InitConfig(base_dir=base, remote=req.remote)
        init_cmd.run()

    _loop_thread = threading.Thread(
        target=_run_loop,
        args=(base, req.model),
        daemon=True,
    )
    _loop_thread.start()

    return {"status": "started", "base_dir": str(base)}


@app.post("/api/sessions/stop")
def stop_session(req: StopRequest):
    base = Path(req.base_dir)
    stop_file = base / PROD_WORKTREE / RALPH_DIR_NAME / "stop.ralph"
    stop_file.write_text("stop requested via API")
    return {"status": "stop_requested"}


# -- websocket -------------------------------------------------------------


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            events = bus.drain()
            for event in events:
                await websocket.send_json(event.to_dict())
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass


# -- loop runner -----------------------------------------------------------


def _run_loop(base_dir: Path, model: str) -> None:
    """Run the Ralph Loop in a background thread with the shared EventBus."""
    loop = Loop()
    loop.cfg = LoopConfig(base_dir=base_dir, model=model)
    loop.event_bus = bus

    try:
        loop.run()
    except SystemExit:
        pass
    finally:
        bus.emit(Event(EventType.LOOP_STOPPED, data={"reason": "thread finished"}))
