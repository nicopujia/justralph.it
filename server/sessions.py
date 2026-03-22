"""Session management: one session = one user project."""

import logging
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from ralph.core.events import EventBus, Event, EventType
from ralph.core.hooks import load_hooks
from ralph.core.ralphy_runner import RalphyRunner, RunnerConfig

import server.db as db

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path("/tmp/ralph-sessions")


@dataclass
class Session:
    """An isolated user project session."""

    id: str
    base_dir: Path
    github_url: str = ""
    name: str = ""  # user-visible label, e.g. "Todo App"
    status: str = "initializing"  # initializing | ready | running | stopped | done | needs_help
    created_at: float = field(default_factory=time.time)
    runner: RalphyRunner | None = field(default=None, repr=False)
    thread: threading.Thread | None = field(default=None, repr=False)
    event_bus: EventBus = field(default_factory=EventBus, repr=False)
    loop_start_time: float | None = None
    iteration_count: int = 0
    share_token: str | None = None
    last_heartbeat_at: float | None = None
    current_task_id: str | None = None

    @property
    def loop_state(self) -> str:
        """Derived loop state for observability endpoint."""
        alive = self.thread is not None and self.thread.is_alive()
        if not alive:
            return "idle"
        if self.status == "needs_help":
            return "stalled"
        if self.current_task_id:
            return "processing_task"
        return "waiting_for_tasks"

    def to_dict(self) -> dict:
        running = self.thread is not None and self.thread.is_alive()
        uptime = None
        if running and self.loop_start_time:
            uptime = round(time.time() - self.loop_start_time, 2)
        last_activity = self.last_heartbeat_at or self.created_at
        return {
            "id": self.id,
            "base_dir": str(self.base_dir),
            "github_url": self.github_url,
            "name": self.name,
            "status": self.status,
            "created_at": self.created_at,
            "running": running,
            "iteration_count": self.iteration_count,
            "uptime_seconds": uptime,
            "share_token": self.share_token,
            "loop_state": self.loop_state,
            "current_task_id": self.current_task_id,
            "loop_elapsed_seconds": uptime,
            "last_activity": last_activity,
        }


# In-memory store (single VPS, demo scope)
_sessions: dict[str, Session] = {}


def _create_github_repo(session_id: str, github_token: str) -> str:
    """Create a GitHub repo via API, return auth-embedded clone URL.

    Returns URL with token embedded (https://token@github.com/user/repo.git)
    so git push works without separate credential setup.
    """
    repo_name = f"ralph-{session_id[:8]}"
    try:
        resp = httpx.post(
            "https://api.github.com/user/repos",
            headers={
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={"name": repo_name, "private": False, "auto_init": False},
            timeout=15,
        )
        if resp.status_code in (200, 201):
            clone_url = resp.json().get("clone_url", "")
            # Embed token in URL for push auth: https://token@github.com/user/repo.git
            if clone_url and github_token:
                clone_url = clone_url.replace(
                    "https://github.com/",
                    f"https://{github_token}@github.com/",
                )
            logger.info("Created GitHub repo %s -> %s", repo_name, clone_url[:40] + "...")
            return clone_url
        logger.warning(
            "GitHub repo creation failed (%s): %s", resp.status_code, resp.text
        )
    except Exception:
        logger.warning("GitHub repo creation error", exc_info=True)
    return ""


def create_session(
    *,
    github_url: str = "",
    github_token: str = "",
    sessions_dir: Path = SESSIONS_DIR,
) -> Session:
    """Create a new isolated session with git repo + ralph scaffolding.

    1. Generate session ID
    2. Create session directory
    3. git init
    4. Auto-create GitHub repo if token provided and no url given
    5. ralph init (creates .ralphy/, tasks.yaml, symlinks)
    6. Add GitHub remote if available
    """
    session_id = uuid.uuid4().hex[:12]
    base_dir = sessions_dir / session_id
    base_dir.mkdir(parents=True, exist_ok=True)

    # git init
    subprocess.run(
        ["git", "init"], cwd=base_dir, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "initial commit"],
        cwd=base_dir, check=True, capture_output=True,
    )
    logger.info("Created git repo at %s", base_dir)

    # Auto-create GitHub repo when token is provided but no explicit url
    if github_token and not github_url:
        github_url = _create_github_repo(session_id, github_token)

    # ralph init scaffolds .ralphy/, tasks.yaml, PROMPT.xml symlink
    from ralph.cmds.init import Init, InitConfig, PACKAGE_ROOT

    init_cmd = Init()
    init_cmd.cfg = InitConfig(base_dir=base_dir, remote=github_url)
    init_cmd.run()

    # Symlink opencode.jsonc too (Agent needs it for --agent ralph)
    oc_src = PACKAGE_ROOT / "opencode.jsonc"
    oc_dst = base_dir / "opencode.jsonc"
    if oc_src.exists() and not oc_dst.exists():
        oc_dst.symlink_to(oc_src)

    # Strip token from URL for display/storage (git remote already has it)
    import re
    display_url = re.sub(r"https://[^@]+@github\.com/", "https://github.com/", github_url)

    session = Session(
        id=session_id,
        base_dir=base_dir,
        github_url=display_url,
        status="ready",
    )
    _sessions[session_id] = session
    db.save_session(session_id, str(base_dir), display_url, "ready", session.created_at)
    logger.info("Session %s ready at %s", session_id, base_dir)
    return session


def get_session(session_id: str) -> Session | None:
    return _sessions.get(session_id)


def list_sessions() -> list[Session]:
    return list(_sessions.values())


def rename_session(session: Session, name: str) -> None:
    """Update the user-visible name of a session."""
    session.name = name
    db.update_session_name(session.id, name)


def start_loop(session: Session) -> None:
    """Start the Ralph Loop for a session in a daemon thread."""
    if session.thread and session.thread.is_alive():
        raise RuntimeError("Loop already running")

    cfg = RunnerConfig(
        base_dir=session.base_dir,
        tasks_file=session.base_dir / "tasks.yaml",
        project_dir=session.base_dir,
        state_file=session.base_dir / ".ralphy" / "state.json",
        stop_file=session.base_dir / ".ralphy" / "stop.ralph",
        restart_file=session.base_dir / ".ralphy" / "restart.ralph",
    )

    # Load hooks (optional)
    hooks = None
    try:
        hooks = load_hooks(cfg)
    except (FileNotFoundError, AttributeError):
        pass

    runner = RalphyRunner(config=cfg, hooks=hooks, bus=session.event_bus)
    session.runner = runner
    session.loop_start_time = time.time()
    session.iteration_count = 0
    session.status = "running"
    db.update_session_status(session.id, "running")

    # Track iteration count + loop observability from events
    def _track_events(event: Event) -> None:
        if event.type == EventType.ITER_STARTED:
            session.iteration_count += 1
        elif event.type == EventType.TASK_HELP:
            session.status = "needs_help"
        elif event.type == EventType.TASK_CLAIMED:
            session.current_task_id = event.data.get("task_id")
        elif event.type == EventType.TASK_DONE:
            session.current_task_id = None
        elif event.type == EventType.LOOP_HEARTBEAT:
            session.last_heartbeat_at = event.timestamp
            session.current_task_id = event.data.get("task_id")
        elif event.type == EventType.LOOP_STALLED:
            session.status = "needs_help"
            session.current_task_id = None
            db.update_session_status(session.id, "needs_help")

    session.event_bus.on(_track_events)

    def _run_with_restart():
        try:
            while True:
                restart = runner.run()
                if not restart:
                    break
                logger.info("Session %s: restarting loop", session.id)
                session.status = "running"
        finally:
            session.status = "done"
            db.update_session_status(session.id, "done")

    t = threading.Thread(target=_run_with_restart, daemon=True)
    session.thread = t
    t.start()


def stop_loop(session: Session) -> None:
    """Write stop signal for a session's loop."""
    if not session.runner or not session.thread or not session.thread.is_alive():
        raise RuntimeError("No loop running")
    session.runner.cfg.stop_file.write_text("stop requested via API")
    session.status = "stopped"
    db.update_session_status(session.id, "stopped")


def restart_loop(session: Session) -> None:
    """Write restart signal for a session's loop."""
    if not session.runner or not session.thread or not session.thread.is_alive():
        raise RuntimeError("No loop running")
    session.runner.cfg.restart_file.write_text("restart requested via API")


def force_stop_loop(session: Session) -> None:
    """Kill the agent subprocess, join the thread, clean up state.

    Used when the graceful stop signal is not working (e.g. stuck subprocess).
    """
    if not session.thread or not session.thread.is_alive():
        raise RuntimeError("No loop running to force stop")

    # Write stop signal so the runner exits on next check
    if session.runner:
        session.runner.cfg.stop_file.write_text("force stop requested via API")

    # Join with timeout -- the stop signal + process kill should unblock
    session.thread.join(timeout=10)

    # If thread is still alive after join, it's truly stuck
    if session.thread.is_alive():
        logger.warning("Session %s: thread still alive after force stop", session.id)

    session.status = "stopped"
    session.current_task_id = None
    session.runner = None
    db.update_session_status(session.id, "stopped")
    logger.info("Session %s: force stopped", session.id)


def kill_current_task(session: Session) -> str | None:
    """Kill the current agent subprocess without stopping the loop.

    The runner will catch the killed process, mark the task BLOCKED,
    and move to the next task.
    Returns the task_id that was killed, or None if nothing was running.
    """
    if not session.runner or not session.thread or not session.thread.is_alive():
        raise RuntimeError("No loop running")

    task_id = session.current_task_id
    if not task_id:
        raise RuntimeError("No task currently being processed")

    # Write a restart signal -- this causes the runner to exit the current
    # iteration (via _check_signals raising _RestartRequested), which kills
    # the subprocess and moves to the next task on re-entry.
    session.runner.cfg.restart_file.write_text(
        f"kill-task requested via API for {task_id}"
    )
    return task_id


def delete_session(session: Session) -> None:
    """Stop loop if running, remove dir, DB row, and memory."""
    import shutil

    if session.thread and session.thread.is_alive():
        stop_loop(session)
        session.thread.join(timeout=5)
    if session.base_dir.exists():
        shutil.rmtree(session.base_dir, ignore_errors=True)
    db.delete_session(session.id)
    _sessions.pop(session.id, None)


def load_sessions_from_db() -> None:
    """Reload sessions from DB on startup. Mark stale 'running' as 'crashed'."""
    rows = db.list_sessions()
    for row in rows:
        sid = row["id"]
        status = row["status"]
        if status == "running":
            status = "crashed"
            db.update_session_status(sid, "crashed")
        session = Session(
            id=sid,
            base_dir=Path(row["base_dir"]),
            github_url=row.get("github_url", ""),
            name=row.get("name", ""),
            status=status,
            created_at=row["created_at"],
            share_token=row.get("share_token"),
        )
        _sessions[sid] = session
    logger.info("Loaded %d sessions from DB", len(rows))
