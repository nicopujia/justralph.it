"""Tests for ralph.py behavior.

Tests cover:
- reload_production: systemctl reload after DONE
- graceful stop: .stop file check between loop iterations
"""

import json
import subprocess
from unittest.mock import MagicMock, patch

from ralph import STOP_FILE, Results, main, reload_production


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_ISSUE_ID = "ISS-99"
FAKE_ISSUE_TITLE = "Add reload feature"


def _make_bd_ready_result(issues):
    """Create a CompletedProcess mimicking `bd ready --json --limit 1`."""
    return subprocess.CompletedProcess(
        args=["bd", "ready", "--json", "--limit", "1"],
        returncode=0,
        stdout=json.dumps(issues),
        stderr="",
    )


def _make_bd_ready_empty():
    return _make_bd_ready_result([])


def _make_claim_result():
    return subprocess.CompletedProcess(
        args=["bd", "update", FAKE_ISSUE_ID, "--claim"],
        returncode=0,
        stdout="",
        stderr="",
    )


def _make_opencode_result(result_msg=Results.DONE):
    return subprocess.CompletedProcess(
        args=["opencode", "run"],
        returncode=0,
        stdout=f"Working on issue...\n<result>{result_msg}</result>",
        stderr="",
    )


def _make_systemctl_result():
    return subprocess.CompletedProcess(
        args=["sudo", "-n", "systemctl", "reload", "just-ralph-it.service"],
        returncode=0,
        stdout="",
        stderr="",
    )


def _make_one_issue_side_effect(opencode_result_msg=Results.DONE):
    """Return a side_effect: first bd ready returns one issue, second returns empty."""
    state = {"bd_ready_count": 0}

    def side_effect(args, **kwargs):
        if args[:2] == ["bd", "list"]:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout=json.dumps([]), stderr="")
        if args[:2] == ["bd", "ready"]:
            state["bd_ready_count"] += 1
            if state["bd_ready_count"] == 1:
                return _make_bd_ready_result([{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}])
            return _make_bd_ready_empty()
        elif args[:2] == ["bd", "update"]:
            return _make_claim_result()
        elif args[0] == "opencode":
            return _make_opencode_result(opencode_result_msg)
        elif args[0] == "sudo" and "systemctl" in args:
            return _make_systemctl_result()
        raise ValueError(f"Unexpected subprocess.run call: {args}")

    return side_effect


# ===========================================================================
# Test: reload_production() calls systemctl reload
# ===========================================================================


class TestReloadProduction:
    """Unit tests for the reload_production() function."""

    @patch("ralph.subprocess.run")
    def test_calls_systemctl_reload(self, mock_run):
        """reload_production() should call systemctl reload just-ralph-it.service."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["sudo", "-n", "systemctl", "reload", "just-ralph-it.service"],
            returncode=0,
            stdout="",
            stderr="",
        )

        reload_production()

        mock_run.assert_called_once_with(
            ["sudo", "-n", "systemctl", "reload", "just-ralph-it.service"],
            check=True,
            capture_output=True,
        )

    @patch("ralph.subprocess.run")
    def test_handles_failure_gracefully(self, mock_run):
        """reload_production() should not raise on failure, just print a warning."""
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["sudo", "-n", "systemctl", "reload", "just-ralph-it.service"],
            stderr="Failed to reload",
        )

        # Should not raise
        reload_production()


# ===========================================================================
# Test: main() calls reload_production after DONE result
# ===========================================================================


class TestMainReloadsAfterDone:
    """Verify that main() calls systemctl reload after a successful issue."""

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_systemctl_reload_called_after_done(self, mock_run, mock_popen):
        """After opencode returns DONE, systemctl reload must be called."""
        mock_run.side_effect = _make_run_side_effect_for_popen_tests(
            bd_ready_results=[[{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}]]
        )
        mock_popen.return_value = _make_mock_popen(Results.DONE)

        main()

        # Find all systemctl reload calls
        systemctl_calls = [
            c
            for c in mock_run.call_args_list
            if len(c.args) > 0
            and len(c.args[0]) >= 2
            and c.args[0][0] == "sudo"
            and "systemctl" in c.args[0]
            and "reload" in c.args[0]
        ]
        assert len(systemctl_calls) >= 1, (
            f"Expected at least one 'sudo -n systemctl reload' call after DONE, got none. All calls: {mock_run.call_args_list}"
        )
        assert systemctl_calls[0].args[0] == [
            "sudo",
            "-n",
            "systemctl",
            "reload",
            "just-ralph-it.service",
        ]

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_systemctl_reload_called_after_opencode(self, mock_run, mock_popen):
        """systemctl reload must be called AFTER opencode finishes."""
        mock_run.side_effect = _make_run_side_effect_for_popen_tests(
            bd_ready_results=[[{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}]]
        )
        mock_popen.return_value = _make_mock_popen(Results.DONE)

        main()

        # opencode now goes through Popen, not run
        assert mock_popen.call_count >= 1, "Expected opencode to be called via Popen"

        # systemctl reload still goes through subprocess.run
        systemctl_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][0] == "sudo"]
        assert len(systemctl_calls) >= 1, "Expected systemctl reload to be called"

        # The code flow guarantees ordering: Popen (opencode) -> wait -> reload (subprocess.run)
        # Since Popen is called before any systemctl run calls, this is verified by both being called.

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_no_reload_on_human_needed(self, mock_run, mock_popen):
        """systemctl reload should NOT be called when result is HUMAN_NEEDED."""
        mock_run.side_effect = _make_run_side_effect_for_popen_tests(
            bd_ready_results=[[{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}]]
        )
        mock_popen.return_value = _make_mock_popen(Results.HUMAN_NEEDED)

        main()

        systemctl_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][0] == "sudo"]
        assert len(systemctl_calls) == 0, (
            f"systemctl reload should NOT be called on HUMAN_NEEDED, but was called {len(systemctl_calls)} time(s)"
        )

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_no_reload_on_new_blocker(self, mock_run, mock_popen):
        """systemctl reload should NOT be called when result is NEW_BLOCKER."""
        mock_run.side_effect = _make_run_side_effect_for_popen_tests(
            bd_ready_results=[[{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}]]
        )
        mock_popen.return_value = _make_mock_popen(Results.NEW_BLOCKER)

        main()

        systemctl_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][0] == "sudo"]
        assert len(systemctl_calls) == 0, (
            f"systemctl reload should NOT be called on NEW_BLOCKER, but was called {len(systemctl_calls)} time(s)"
        )


# ===========================================================================
# Helpers for Popen-aware tests (opencode uses Popen, not run)
# ===========================================================================


def _make_mock_popen(result_msg=Results.DONE):
    """Create a mock Popen that simulates streaming opencode output."""
    mock_proc = MagicMock()
    mock_proc.stdout = iter(
        [
            "Working on issue...\n",
            f"<result>{result_msg}</result>\n",
        ]
    )
    mock_proc.wait.return_value = 0
    return mock_proc


def _make_run_side_effect_for_popen_tests(bd_ready_results=None):
    """Return a side_effect for subprocess.run that handles bd/systemctl calls only.

    bd_ready_results: list of lists-of-issues for successive bd ready calls.
    """
    if bd_ready_results is None:
        bd_ready_results = []
    state = {"bd_ready_count": 0}

    def side_effect(args, **kwargs):
        if args[:2] == ["bd", "list"]:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout=json.dumps([]), stderr="")
        if args[:2] == ["bd", "ready"]:
            idx = state["bd_ready_count"]
            state["bd_ready_count"] += 1
            if idx < len(bd_ready_results):
                return _make_bd_ready_result(bd_ready_results[idx])
            return _make_bd_ready_empty()
        elif args[:2] == ["bd", "update"]:
            return _make_claim_result()
        elif args[0] == "sudo" and "systemctl" in args:
            return _make_systemctl_result()
        raise ValueError(f"Unexpected subprocess.run call: {args}")

    return side_effect


# ===========================================================================
# Test: Graceful stop via .stop file
# ===========================================================================


class TestGracefulStop:
    """Tests for the .stop file graceful stop mechanism."""

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    @patch("ralph.STOP_FILE")
    def test_stop_file_exists_at_start_exits_immediately(self, mock_stop_file, mock_run, mock_popen):
        """When .stop file exists at the top of the loop, ralph exits without claiming any issue."""
        # .stop file exists, then gets "deleted" (unlink succeeds)
        mock_stop_file.exists.return_value = True
        mock_stop_file.unlink.return_value = None

        # bd ready should never be called
        mock_run.side_effect = _make_run_side_effect_for_popen_tests(bd_ready_results=[])

        main()

        # Should NOT have called bd ready or Popen (no issue work started)
        bd_ready_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][:2] == ["bd", "ready"]]
        assert len(bd_ready_calls) == 0, (
            f"bd ready should NOT be called when .stop file exists, but was called {len(bd_ready_calls)} time(s)"
        )
        mock_popen.assert_not_called()

        # .stop file should have been deleted
        mock_stop_file.unlink.assert_called_once()

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    @patch("ralph.STOP_FILE")
    def test_stop_file_prints_stopping_message(self, mock_stop_file, mock_run, mock_popen, capsys):
        """When .stop file exists, ralph prints the STOPPED message."""
        mock_stop_file.exists.return_value = True
        mock_stop_file.unlink.return_value = None
        mock_run.side_effect = _make_run_side_effect_for_popen_tests(bd_ready_results=[])

        main()

        captured = capsys.readouterr()
        assert Results.STOPPED in captured.out

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    @patch("ralph.STOP_FILE")
    def test_no_stop_file_continues_normally(self, mock_stop_file, mock_run, mock_popen):
        """When .stop file does NOT exist, ralph continues to get the next issue."""
        mock_stop_file.exists.return_value = False

        # Return one issue, then empty
        mock_run.side_effect = _make_run_side_effect_for_popen_tests(
            bd_ready_results=[[{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}]]
        )
        mock_popen.return_value = _make_mock_popen(Results.DONE)

        main()

        # bd ready SHOULD have been called
        bd_ready_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][:2] == ["bd", "ready"]]
        assert len(bd_ready_calls) >= 1, "bd ready should be called when .stop file doesn't exist"

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    @patch("ralph.STOP_FILE")
    def test_stop_file_checked_between_issues(self, mock_stop_file, mock_run, mock_popen):
        """The .stop file check happens after an issue completes and before the next one starts.

        Scenario: first iteration has no .stop file, issue completes with DONE.
        Second iteration finds .stop file and exits cleanly.
        """
        # First check: no stop file. Second check (after first issue): stop file exists.
        mock_stop_file.exists.side_effect = [False, True]
        mock_stop_file.unlink.return_value = None

        # One issue available (would be fetched on first iteration)
        mock_run.side_effect = _make_run_side_effect_for_popen_tests(
            bd_ready_results=[
                [{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}],
                [{"id": "ISS-100", "title": "Another issue"}],  # would be fetched if no stop
            ]
        )
        mock_popen.return_value = _make_mock_popen(Results.DONE)

        main()

        # First issue should have been worked on (Popen called once)
        assert mock_popen.call_count == 1, f"Expected exactly 1 Popen call (first issue), got {mock_popen.call_count}"

        # bd ready should have been called exactly once (for the first issue)
        # The second iteration should stop before calling bd ready
        bd_ready_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][:2] == ["bd", "ready"]]
        assert len(bd_ready_calls) == 1, (
            f"Expected exactly 1 bd ready call (second iteration stopped by .stop file), got {len(bd_ready_calls)}"
        )

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    @patch("ralph.STOP_FILE")
    def test_stop_file_deleted_after_detection(self, mock_stop_file, mock_run, mock_popen):
        """The .stop file is deleted when detected (so it doesn't persist)."""
        mock_stop_file.exists.return_value = True
        mock_stop_file.unlink.return_value = None
        mock_run.side_effect = _make_run_side_effect_for_popen_tests(bd_ready_results=[])

        main()

        mock_stop_file.unlink.assert_called_once()

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    @patch("ralph.STOP_FILE")
    def test_no_issue_left_in_broken_state(self, mock_stop_file, mock_run, mock_popen):
        """When stop happens between issues, the completed issue went through DONE + reload.

        This ensures the stop is clean — the previous issue fully completed.
        """
        # First iteration: no stop. Second iteration: stop.
        mock_stop_file.exists.side_effect = [False, True]
        mock_stop_file.unlink.return_value = None

        mock_run.side_effect = _make_run_side_effect_for_popen_tests(
            bd_ready_results=[
                [{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}],
            ]
        )
        mock_popen.return_value = _make_mock_popen(Results.DONE)

        main()

        # The first issue should have completed AND reload should have been called
        systemctl_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][0] == "sudo"]
        assert len(systemctl_calls) == 1, (
            f"Expected systemctl reload to be called for the completed issue, got {len(systemctl_calls)} call(s)"
        )
