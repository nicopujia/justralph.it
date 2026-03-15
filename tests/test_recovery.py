"""Tests for startup recovery: restart bdui sidecars and resume ralph.py (TDD).

Feature: When the web app starts, recover_processes(app) reads the SQLite DB and:
1. Restarts the bdui sidecar for every project that has a bdui_port and vps_path
2. For any project where ralph_running=1, resumes ralph.py (spawns it with
   cwd=vps_path), stores the process in ralph_processes, and starts a watcher thread

This ensures crash recovery after VPS reboots.
"""

import os
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch

from app import create_app
from app.recovery import recover_processes

# ---------------------------------------------------------------------------
# Helpers (same pattern as test_ralph_launch.py)
# ---------------------------------------------------------------------------


def _make_app(**extra_config):
    """Create app with a temp DB and return (app, db_path, db_fd).

    Patches recover_processes during app creation so the tests can call it
    explicitly with controlled mocks.
    """
    db_fd, db_path = tempfile.mkstemp()
    with patch("app.recovery.recover_processes"):
        app = create_app({"DATABASE": db_path, "TESTING": True, **extra_config})
    return app, db_path, db_fd


def _cleanup(db_fd, db_path):
    os.close(db_fd)
    os.unlink(db_path)


def _insert_project(
    db_path,
    name="test-project",
    slug="test-project",
    ralph_running=0,
    vps_path="/home/nico/projects/test-project",
    bdui_port=None,
):
    """Insert a project directly into the DB."""
    db = sqlite3.connect(db_path)
    db.execute(
        """INSERT INTO projects (name, slug, ralph_running, vps_path, bdui_port)
           VALUES (?, ?, ?, ?, ?)""",
        (name, slug, ralph_running, vps_path, bdui_port),
    )
    db.commit()
    db.close()


# ===========================================================================
# bdui recovery
# ===========================================================================


class TestBduiRecovery:
    """recover_processes restarts bdui sidecars for all projects with port+path."""

    @patch("app.recovery.start_bdui")
    def test_restarts_bdui_for_all_projects(self, mock_start_bdui):
        """Calls start_bdui for each project that has bdui_port and vps_path."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(
                db_path, name="proj-a", slug="proj-a", vps_path="/home/nico/projects/proj-a", bdui_port=9001
            )
            _insert_project(
                db_path, name="proj-b", slug="proj-b", vps_path="/home/nico/projects/proj-b", bdui_port=9002
            )

            recover_processes(app)

            assert mock_start_bdui.call_count == 2
            mock_start_bdui.assert_any_call("/home/nico/projects/proj-a", 9001)
            mock_start_bdui.assert_any_call("/home/nico/projects/proj-b", 9002)
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.recovery.start_bdui")
    def test_no_projects_does_not_crash(self, mock_start_bdui):
        """Empty DB causes no errors and no start_bdui calls."""
        app, db_path, db_fd = _make_app()
        try:
            recover_processes(app)
            mock_start_bdui.assert_not_called()
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.recovery.start_bdui")
    def test_skips_projects_without_port(self, mock_start_bdui):
        """Projects with vps_path but no bdui_port are skipped."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(
                db_path, name="no-port", slug="no-port", vps_path="/home/nico/projects/no-port", bdui_port=None
            )

            recover_processes(app)

            mock_start_bdui.assert_not_called()
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.recovery.start_bdui")
    def test_skips_projects_without_vps_path(self, mock_start_bdui):
        """Projects with bdui_port but no vps_path are skipped."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(db_path, name="no-path", slug="no-path", vps_path=None, bdui_port=9001)

            recover_processes(app)

            mock_start_bdui.assert_not_called()
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# ralph recovery
# ===========================================================================


class TestRalphRecovery:
    """recover_processes resumes ralph.py for projects with ralph_running=1."""

    @patch("app.recovery.threading.Thread")
    @patch("app.recovery.subprocess.Popen")
    @patch("app.recovery.start_bdui")
    def test_spawns_ralph_for_running_projects(self, mock_start_bdui, mock_popen, mock_thread):
        """Spawns ralph.py subprocess with correct cwd for ralph_running=1 projects."""
        mock_process = MagicMock()
        mock_process.stdout = iter([])
        mock_popen.return_value = mock_process
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(
                db_path,
                name="active",
                slug="active",
                ralph_running=1,
                vps_path="/home/nico/projects/active",
                bdui_port=9001,
            )

            recover_processes(app)

            mock_popen.assert_called_once()
            call_kwargs = mock_popen.call_args
            assert call_kwargs.kwargs.get("cwd") == "/home/nico/projects/active"
            args = call_kwargs[0][0] if call_kwargs[0] else call_kwargs.kwargs.get("args", [])
            joined_args = " ".join(str(a) for a in args)
            assert "ralph.py" in joined_args
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.recovery.threading.Thread")
    @patch("app.recovery.subprocess.Popen")
    @patch("app.recovery.start_bdui")
    def test_spawns_ralph_with_unbuffered_env(self, mock_start_bdui, mock_popen, mock_thread):
        """Spawns ralph.py with PYTHONUNBUFFERED=1 in the environment for real-time output."""
        mock_process = MagicMock()
        mock_process.stdout = iter([])
        mock_popen.return_value = mock_process
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(
                db_path,
                name="active",
                slug="active",
                ralph_running=1,
                vps_path="/home/nico/projects/active",
                bdui_port=9001,
            )

            recover_processes(app)

            mock_popen.assert_called_once()
            call_kwargs = mock_popen.call_args
            env = call_kwargs.kwargs.get("env") or call_kwargs[1].get("env")
            assert env is not None, "Popen should be called with an env parameter"
            assert env.get("PYTHONUNBUFFERED") == "1", (
                f"PYTHONUNBUFFERED should be '1' in env, got: {env.get('PYTHONUNBUFFERED')}"
            )
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.recovery.threading.Thread")
    @patch("app.recovery.subprocess.Popen")
    @patch("app.recovery.start_bdui")
    def test_stores_process_in_ralph_processes(self, mock_start_bdui, mock_popen, mock_thread):
        """After recovery, the spawned process is stored in routes.ralph_processes."""
        mock_process = MagicMock()
        mock_process.stdout = iter([])
        mock_popen.return_value = mock_process
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(
                db_path,
                name="active",
                slug="active",
                ralph_running=1,
                vps_path="/home/nico/projects/active",
                bdui_port=9001,
            )

            from app import routes

            routes.ralph_processes.clear()

            recover_processes(app)

            assert "active" in routes.ralph_processes
            assert routes.ralph_processes["active"] is mock_process
        finally:
            from app import routes

            routes.ralph_processes.clear()
            _cleanup(db_fd, db_path)

    @patch("app.recovery.threading.Thread")
    @patch("app.recovery.subprocess.Popen")
    @patch("app.recovery.start_bdui")
    def test_starts_watcher_thread(self, mock_start_bdui, mock_popen, mock_thread):
        """A daemon watcher thread is started for each recovered ralph process."""
        mock_process = MagicMock()
        mock_process.stdout = iter([])
        mock_popen.return_value = mock_process
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(
                db_path,
                name="active",
                slug="active",
                ralph_running=1,
                vps_path="/home/nico/projects/active",
                bdui_port=9001,
            )

            recover_processes(app)

            mock_thread.assert_called_once()
            call_kwargs = mock_thread.call_args
            assert call_kwargs.kwargs.get("daemon") is True
            mock_thread_instance.start.assert_called_once()
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.recovery.threading.Thread")
    @patch("app.recovery.subprocess.Popen")
    @patch("app.recovery.start_bdui")
    def test_does_not_spawn_for_ralph_running_0(self, mock_start_bdui, mock_popen, mock_thread):
        """Projects with ralph_running=0 do NOT get ralph.py spawned."""
        app, db_path, db_fd = _make_app()
        try:
            _insert_project(
                db_path, name="idle", slug="idle", ralph_running=0, vps_path="/home/nico/projects/idle", bdui_port=9001
            )

            recover_processes(app)

            mock_popen.assert_not_called()
            mock_thread.assert_not_called()
        finally:
            _cleanup(db_fd, db_path)


# ===========================================================================
# Multiple projects / mixed scenarios
# ===========================================================================


class TestRecoveryMultipleProjects:
    """Recovery handles a mix of projects correctly."""

    @patch("app.recovery.threading.Thread")
    @patch("app.recovery.subprocess.Popen")
    @patch("app.recovery.start_bdui")
    def test_mixed_projects(self, mock_start_bdui, mock_popen, mock_thread):
        """Multiple projects: bdui restarted for all with port+path, ralph only for running=1."""
        mock_process = MagicMock()
        mock_process.stdout = iter([])
        mock_popen.return_value = mock_process
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        app, db_path, db_fd = _make_app()
        try:
            # Project A: has port, ralph_running=1 -> bdui + ralph
            _insert_project(
                db_path,
                name="proj-a",
                slug="proj-a",
                ralph_running=1,
                vps_path="/home/nico/projects/proj-a",
                bdui_port=9001,
            )
            # Project B: has port, ralph_running=0 -> bdui only
            _insert_project(
                db_path,
                name="proj-b",
                slug="proj-b",
                ralph_running=0,
                vps_path="/home/nico/projects/proj-b",
                bdui_port=9002,
            )
            # Project C: no port -> skip bdui, ralph_running=0 -> skip ralph
            _insert_project(
                db_path,
                name="proj-c",
                slug="proj-c",
                ralph_running=0,
                vps_path="/home/nico/projects/proj-c",
                bdui_port=None,
            )

            recover_processes(app)

            # bdui started for A and B (have port + path), not C
            assert mock_start_bdui.call_count == 2
            mock_start_bdui.assert_any_call("/home/nico/projects/proj-a", 9001)
            mock_start_bdui.assert_any_call("/home/nico/projects/proj-b", 9002)

            # ralph spawned only for A (ralph_running=1)
            mock_popen.assert_called_once()
            call_kwargs = mock_popen.call_args
            assert call_kwargs.kwargs.get("cwd") == "/home/nico/projects/proj-a"
        finally:
            from app import routes

            routes.ralph_processes.clear()
            _cleanup(db_fd, db_path)


# ===========================================================================
# Error resilience
# ===========================================================================


class TestRecoveryErrorResilience:
    """Recovery continues even if individual steps fail."""

    @patch("app.recovery.start_bdui")
    def test_bdui_failure_does_not_block_others(self, mock_start_bdui):
        """If start_bdui fails for one project, recovery continues for the rest."""
        mock_start_bdui.side_effect = [
            OSError("bdui not found"),  # first project fails
            MagicMock(),  # second project succeeds
        ]

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(
                db_path, name="fail-proj", slug="fail-proj", vps_path="/home/nico/projects/fail-proj", bdui_port=9001
            )
            _insert_project(
                db_path, name="ok-proj", slug="ok-proj", vps_path="/home/nico/projects/ok-proj", bdui_port=9002
            )

            # Should not raise — failures are caught
            recover_processes(app)

            assert mock_start_bdui.call_count == 2
        finally:
            _cleanup(db_fd, db_path)

    @patch("app.recovery.threading.Thread")
    @patch("app.recovery.subprocess.Popen")
    @patch("app.recovery.start_bdui")
    def test_bdui_failure_does_not_block_ralph_recovery(self, mock_start_bdui, mock_popen, mock_thread):
        """If start_bdui fails, ralph recovery still runs for ralph_running=1 projects."""
        mock_start_bdui.side_effect = OSError("bdui not found")
        mock_process = MagicMock()
        mock_process.stdout = iter([])
        mock_popen.return_value = mock_process
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        app, db_path, db_fd = _make_app()
        try:
            _insert_project(
                db_path, name="proj", slug="proj", ralph_running=1, vps_path="/home/nico/projects/proj", bdui_port=9001
            )

            recover_processes(app)

            # bdui was attempted (and failed)
            mock_start_bdui.assert_called_once()
            # ralph was still spawned
            mock_popen.assert_called_once()
        finally:
            from app import routes

            routes.ralph_processes.clear()
            _cleanup(db_fd, db_path)


# ===========================================================================
# Integration: create_app calls recover_processes
# ===========================================================================


class TestRecoveryIntegration:
    """Verify that create_app() triggers recover_processes()."""

    @patch("app.recovery.recover_processes")
    def test_create_app_calls_recover_processes(self, mock_recover):
        """Creating the app calls recover_processes with the app instance."""
        db_fd, db_path = tempfile.mkstemp()
        try:
            app = create_app({"DATABASE": db_path, "TESTING": True})
            mock_recover.assert_called_once_with(app)
        finally:
            os.close(db_fd)
            os.unlink(db_path)
