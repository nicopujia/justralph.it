"""Session management: one session = one user project."""

import logging
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from ralph.core.events import EventBus, EventType
from ralph.core.hooks import load_hooks
from ralph.core.ralphy_runner import RalphyRunner, RunnerConfig

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path("/tmp/ralph-sessions")


@dataclass
class Session:
    """An isolated user project session."""

    id: str
    base_dir: Path
    github_url: str = ""
    status: str = "initializing"  # initializing | ready | running | stopped | done | needs_help
    created_at: float = field(default_factory=time.time)
    runner: RalphyRunner | None = field(default=None, repr=False)
    thread: threading.Thread | None = field(default=None, repr=False)
    event_bus: EventBus = field(default_factory=EventBus, repr=False)
    loop_start_time: float | None = None
    iteration_count: int = 0

    def to_dict(self) -> dict:
        running = self.thread is not None and self.thread.is_alive()
        uptime = None
        if running and self.loop_start_time:
            uptime = round(time.time() - self.loop_start_time, 2)
        return {
            "id": self.id,
            "base_dir": str(self.base_dir),
            "github_url": self.github_url,
            "status": self.status,
            "created_at": self.created_at,
            "running": running,
            "iteration_count": self.iteration_count,
            "uptime_seconds": uptime,
        }


# In-memory store (single VPS, demo scope)
_sessions: dict[str, Session] = {}


def _create_github_repo(session_id: str, github_token: str) -> str:
    """Create a GitHub repo via API, return clone_url or empty string on failure."""
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
            logger.info("Created GitHub repo %s -> %s", repo_name, clone_url)
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

    session = Session(
        id=session_id,
        base_dir=base_dir,
        github_url=github_url,
        status="ready",
    )
    _sessions[session_id] = session
    logger.info("Session %s ready at %s", session_id, base_dir)
    return session


def get_session(session_id: str) -> Session | None:
    return _sessions.get(session_id)


def list_sessions() -> list[Session]:
    return list(_sessions.values())


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

    # Track iteration count from events
    def _track_events(event):
        if event.type == EventType.ITER_STARTED:
            session.iteration_count += 1
        elif event.type == EventType.TASK_HELP:
            session.status = "needs_help"

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

    t = threading.Thread(target=_run_with_restart, daemon=True)
    session.thread = t
    t.start()


def stop_loop(session: Session) -> None:
    """Write stop signal for a session's loop."""
    if not session.runner or not session.thread or not session.thread.is_alive():
        raise RuntimeError("No loop running")
    session.runner.cfg.stop_file.write_text("stop requested via API")
    session.status = "stopped"


def restart_loop(session: Session) -> None:
    """Write restart signal for a session's loop."""
    if not session.runner or not session.thread or not session.thread.is_alive():
        raise RuntimeError("No loop running")
    session.runner.cfg.restart_file.write_text("restart requested via API")
