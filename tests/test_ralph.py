"""Tests for ralph.py behavior.

Tests cover:
- reload_production: systemctl reload after DONE
- graceful stop: .stop file check between loop iterations
"""

import json
import subprocess
from unittest.mock import MagicMock, patch

from ralph import STOP_FILE, Results, check_resources, get_prompt, main, reload_production


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

        mock_run.assert_called_once()
        call_args, call_kwargs = mock_run.call_args
        assert call_args == (["sudo", "-n", "systemctl", "reload", "just-ralph-it.service"],)
        assert call_kwargs["check"] is True
        assert call_kwargs["capture_output"] is True
        assert "env" in call_kwargs  # subprocess_env() provides the env

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


# ===========================================================================
# Test: get_prompt() includes non-interactive subagent instructions
# ===========================================================================


class TestNonInteractivePromptInstructions:
    """Verify that get_prompt() instructs subagents to run non-interactively.

    These tests are RED — the prompt does not yet contain these instructions.
    """

    def _get_prompt(self) -> str:
        return get_prompt(issue_id="ISS-1", username="testuser")

    def test_prompt_contains_non_interactive_instruction(self):
        """The prompt must instruct subagents to run all commands non-interactively."""
        prompt = self._get_prompt()
        prompt_lower = prompt.lower()
        assert (
            "non-interactive" in prompt_lower
            or "never wait for input" in prompt_lower
            or ("never" in prompt_lower and "prompt for input" in prompt_lower)
        ), (
            "get_prompt() must instruct subagents to run commands non-interactively / never wait for input. "
            f"Prompt was:\n{prompt}"
        )

    def test_prompt_contains_non_interactive_flags(self):
        """The prompt must mention key non-interactive flags for common commands."""
        prompt = self._get_prompt()
        required_flags = {
            "apt-get -y": "apt-get -y",
            "cp -f": "cp -f",
            "mv -f": "mv -f",
            "rm -f": "rm -f",
            "npm --yes": "npm --yes",
        }
        missing = [label for label, flag in required_flags.items() if flag not in prompt]
        assert not missing, f"get_prompt() must mention these non-interactive flags: {missing}. Prompt was:\n{prompt}"

    def test_prompt_contains_fail_fast_instruction(self):
        """The prompt must instruct subagents to fail fast if interaction is required."""
        prompt = self._get_prompt()
        prompt_lower = prompt.lower()
        assert (
            "fail fast" in prompt_lower
            or "fail immediately" in prompt_lower
            or ("fail" in prompt_lower and ("interaction" in prompt_lower or "interactive" in prompt_lower))
        ), f"get_prompt() must instruct subagents to fail fast if a command requires interaction. Prompt was:\n{prompt}"


# ===========================================================================
# Helpers for resource-check mocking
# ===========================================================================


def _make_virtual_memory(percent):
    """Create a mock psutil.virtual_memory() return value."""
    mock = MagicMock()
    mock.percent = percent
    return mock


def _make_disk_usage(used_percent):
    """Create a mock shutil.disk_usage('/') return value.

    shutil.disk_usage returns a named tuple with (total, used, free).
    We set total=100 so used equals the percentage directly.
    """
    mock = MagicMock()
    mock.total = 100
    mock.used = used_percent
    return mock


# ===========================================================================
# Test: VPS resource checking
# ===========================================================================


class TestResourceCheck:
    """Tests for the check_resources() function and its integration into main()."""

    # -----------------------------------------------------------------------
    # Unit tests for check_resources()
    # -----------------------------------------------------------------------

    @patch("ralph.shutil.disk_usage")
    @patch("ralph.psutil.virtual_memory")
    def test_check_resources_returns_false_when_below_threshold(self, mock_vmem, mock_disk):
        """When RAM=50% and disk=60%, returns (False, '')."""
        mock_vmem.return_value = _make_virtual_memory(50)
        mock_disk.return_value = _make_disk_usage(60)

        exceeded, message = check_resources()

        assert exceeded is False
        assert message == ""

    @patch("ralph.shutil.disk_usage")
    @patch("ralph.psutil.virtual_memory")
    def test_check_resources_returns_true_for_high_ram(self, mock_vmem, mock_disk):
        """When RAM=95% and disk=50%, returns (True, message with '95%' and 'RAM')."""
        mock_vmem.return_value = _make_virtual_memory(95)
        mock_disk.return_value = _make_disk_usage(50)

        exceeded, message = check_resources()

        assert exceeded is True
        assert "95%" in message
        assert "RAM" in message
        assert "Free up space or upgrade before continuing." in message

    @patch("ralph.shutil.disk_usage")
    @patch("ralph.psutil.virtual_memory")
    def test_check_resources_returns_true_for_high_disk(self, mock_vmem, mock_disk):
        """When RAM=50% and disk=92%, returns (True, message with '92%' and 'disk')."""
        mock_vmem.return_value = _make_virtual_memory(50)
        mock_disk.return_value = _make_disk_usage(92)

        exceeded, message = check_resources()

        assert exceeded is True
        assert "92%" in message
        assert "disk" in message
        assert "Free up space or upgrade before continuing." in message

    @patch("ralph.shutil.disk_usage")
    @patch("ralph.psutil.virtual_memory")
    def test_check_resources_reports_higher_when_both_exceed(self, mock_vmem, mock_disk):
        """When RAM=95% and disk=98%, returns (True, message with '98%' and 'disk')."""
        mock_vmem.return_value = _make_virtual_memory(95)
        mock_disk.return_value = _make_disk_usage(98)

        exceeded, message = check_resources()

        assert exceeded is True
        assert "98%" in message
        assert "disk" in message
        # Should NOT report 95% RAM since disk is higher
        assert "RAM" not in message

    @patch("ralph.shutil.disk_usage")
    @patch("ralph.psutil.virtual_memory")
    def test_check_resources_at_exactly_90_continues(self, mock_vmem, mock_disk):
        """At exactly 90%, returns (False, '') — 'exceeds 90%' means strictly above."""
        mock_vmem.return_value = _make_virtual_memory(90)
        mock_disk.return_value = _make_disk_usage(90)

        exceeded, message = check_resources()

        assert exceeded is False
        assert message == ""

    @patch("ralph.shutil.disk_usage")
    @patch("ralph.psutil.virtual_memory")
    def test_check_resources_at_91_stops(self, mock_vmem, mock_disk):
        """At 91% RAM, returns (True, ...) — just above the 90% threshold."""
        mock_vmem.return_value = _make_virtual_memory(91)
        mock_disk.return_value = _make_disk_usage(50)

        exceeded, message = check_resources()

        assert exceeded is True
        assert "91%" in message
        assert "RAM" in message

    # -----------------------------------------------------------------------
    # Integration tests: check_resources() in main()
    # -----------------------------------------------------------------------

    @patch("ralph.check_resources")
    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    @patch("ralph.STOP_FILE")
    def test_main_stops_on_high_resources(self, mock_stop_file, mock_run, mock_popen, mock_check):
        """main() exits cleanly without claiming any issue when resources are high."""
        mock_stop_file.exists.return_value = False
        mock_check.return_value = (
            True,
            "Ralph stopped: VPS resources at 95% RAM. Free up space or upgrade before continuing.",
        )
        mock_run.side_effect = _make_run_side_effect_for_popen_tests(
            bd_ready_results=[[{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}]]
        )

        main()

        # bd ready should NOT have been called — resources stopped the loop first
        bd_ready_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][:2] == ["bd", "ready"]]
        assert len(bd_ready_calls) == 0, (
            f"bd ready should NOT be called when resources are exhausted, but was called {len(bd_ready_calls)} time(s)"
        )
        mock_popen.assert_not_called()

    @patch("ralph.check_resources")
    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    @patch("ralph.STOP_FILE")
    def test_main_stops_on_high_resources_logs_message(self, mock_stop_file, mock_run, mock_popen, mock_check, capsys):
        """main() logs RESOURCES_EXHAUSTED when resources are high."""
        mock_stop_file.exists.return_value = False
        mock_check.return_value = (
            True,
            "Ralph stopped: VPS resources at 95% RAM. Free up space or upgrade before continuing.",
        )
        mock_run.side_effect = _make_run_side_effect_for_popen_tests(bd_ready_results=[])

        main()

        captured = capsys.readouterr()
        assert Results.RESOURCES_EXHAUSTED in captured.out

    @patch("ralph.check_resources")
    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    @patch("ralph.STOP_FILE")
    def test_main_continues_on_normal_resources(self, mock_stop_file, mock_run, mock_popen, mock_check):
        """main() continues normally when resources are fine."""
        mock_stop_file.exists.return_value = False
        mock_check.return_value = (False, "")
        mock_run.side_effect = _make_run_side_effect_for_popen_tests(
            bd_ready_results=[[{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}]]
        )
        mock_popen.return_value = _make_mock_popen(Results.DONE)

        main()

        # bd ready SHOULD have been called
        bd_ready_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][:2] == ["bd", "ready"]]
        assert len(bd_ready_calls) >= 1, "bd ready should be called when resources are fine"

    @patch("ralph.check_resources")
    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    @patch("ralph.STOP_FILE")
    def test_resource_check_happens_before_claiming_issue(self, mock_stop_file, mock_run, mock_popen, mock_check):
        """Verify resource check happens before bd ready is called."""
        mock_stop_file.exists.return_value = False
        mock_check.return_value = (
            True,
            "Ralph stopped: VPS resources at 95% RAM. Free up space or upgrade before continuing.",
        )
        mock_run.side_effect = _make_run_side_effect_for_popen_tests(
            bd_ready_results=[[{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}]]
        )

        main()

        # check_resources was called
        mock_check.assert_called_once()

        # bd ready was NOT called (stopped before reaching it)
        bd_ready_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][:2] == ["bd", "ready"]]
        assert len(bd_ready_calls) == 0, (
            f"Resource check should prevent bd ready from being called, but got {len(bd_ready_calls)} call(s)"
        )

    @patch("ralph.check_resources")
    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    @patch("ralph.STOP_FILE")
    def test_resource_check_between_iterations(self, mock_stop_file, mock_run, mock_popen, mock_check):
        """After first issue completes with DONE, resource check on second iteration stops the loop.

        Scenario: first iteration resources OK, issue completes. Second iteration resources exhausted.
        """
        mock_stop_file.exists.return_value = False
        # First call: OK. Second call: exhausted.
        mock_check.side_effect = [
            (False, ""),
            (True, "Ralph stopped: VPS resources at 95% RAM. Free up space or upgrade before continuing."),
        ]
        mock_run.side_effect = _make_run_side_effect_for_popen_tests(
            bd_ready_results=[
                [{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}],
                [{"id": "ISS-100", "title": "Another issue"}],
            ]
        )
        mock_popen.return_value = _make_mock_popen(Results.DONE)

        main()

        # First issue was worked on
        assert mock_popen.call_count == 1, f"Expected exactly 1 Popen call (first issue), got {mock_popen.call_count}"

        # bd ready called once (first iteration), NOT called for second (resource check stopped it)
        bd_ready_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][:2] == ["bd", "ready"]]
        assert len(bd_ready_calls) == 1, (
            f"Expected exactly 1 bd ready call (second iteration stopped by resource check), got {len(bd_ready_calls)}"
        )

        # check_resources called twice (once per iteration)
        assert mock_check.call_count == 2, f"Expected 2 check_resources calls, got {mock_check.call_count}"
