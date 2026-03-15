"""Startup recovery: restart bdui sidecars and resume ralph loops after crash/reboot."""

import os
import sqlite3
import subprocess
import sys
import threading

from . import PROJECT_ROOT
from .projects import start_bdui
from .sse import publish


def recover_processes(app):
    """Recover bdui sidecars and ralph.py processes from DB state.

    Called during create_app() to handle crash recovery.
    """
    db_path = app.config["DATABASE"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT slug, vps_path, bdui_port, ralph_running FROM projects").fetchall()
    conn.close()

    from . import routes

    for row in rows:
        slug = row["slug"]
        vps_path = row["vps_path"]
        bdui_port = row["bdui_port"]
        ralph_running = row["ralph_running"]

        # Restart bdui sidecar if project has both port and path
        if vps_path and bdui_port:
            try:
                start_bdui(vps_path, bdui_port)
            except Exception:
                pass

        # Resume ralph.py if it was running before crash
        if ralph_running and vps_path:
            try:
                ralph_py_path = os.path.join(PROJECT_ROOT, "ralph.py")
                env = {**os.environ, "PYTHONUNBUFFERED": "1"}
                process = subprocess.Popen(
                    [sys.executable, ralph_py_path],
                    cwd=vps_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=env,
                )
                routes.ralph_processes[slug] = process

                def _watch_ralph(process=process, slug=slug):
                    last_line = ""
                    if process.stdout:
                        for raw_line in process.stdout:
                            decoded = (
                                raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
                            )
                            stripped = decoded.strip()
                            if stripped:
                                last_line = stripped
                    rc = process.wait()
                    if not isinstance(rc, int):
                        return
                    if routes.ralph_processes.get(slug) is not process:
                        return
                    try:
                        conn = sqlite3.connect(db_path)
                        conn.execute(
                            "UPDATE projects SET ralph_running = 0 WHERE slug = ?",
                            (slug,),
                        )
                        conn.commit()
                        conn.close()
                    except Exception:
                        pass
                    if last_line == "NO MORE ISSUES LEFT":
                        reason = "all_done"
                    elif last_line == "Stopping as requested.":
                        reason = "stopped"
                    else:
                        reason = "human_needed"
                    publish(slug, "ralph_stopped", {"reason": reason})
                    routes.ralph_processes.pop(slug, None)

                t = threading.Thread(target=_watch_ralph, daemon=True)
                t.start()
            except Exception:
                pass
