"""Tests for ralph.py reload_production behavior.

After successfully completing an issue (Results.DONE), ralph.py should
call reload_production() which runs `systemctl reload just-ralph-it.service`
so that code changes go live in production.
"""

import json
import subprocess
from unittest.mock import patch

from ralph import Results, main, reload_production


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
        args=["systemctl", "reload", "just-ralph-it.service"],
        returncode=0,
        stdout="",
        stderr="",
    )


def _make_one_issue_side_effect(opencode_result_msg=Results.DONE):
    """Return a side_effect: first bd ready returns one issue, second returns empty."""
    state = {"bd_ready_count": 0}

    def side_effect(args, **kwargs):
        if args[:2] == ["bd", "ready"]:
            state["bd_ready_count"] += 1
            if state["bd_ready_count"] == 1:
                return _make_bd_ready_result([{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}])
            return _make_bd_ready_empty()
        elif args[:2] == ["bd", "update"]:
            return _make_claim_result()
        elif args[0] == "opencode":
            return _make_opencode_result(opencode_result_msg)
        elif args[0] == "systemctl":
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
            args=["systemctl", "reload", "just-ralph-it.service"],
            returncode=0,
            stdout="",
            stderr="",
        )

        reload_production()

        mock_run.assert_called_once_with(
            ["systemctl", "reload", "just-ralph-it.service"],
            check=True,
            capture_output=True,
        )

    @patch("ralph.subprocess.run")
    def test_handles_failure_gracefully(self, mock_run):
        """reload_production() should not raise on failure, just print a warning."""
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["systemctl", "reload", "just-ralph-it.service"],
            stderr="Failed to reload",
        )

        # Should not raise
        reload_production()


# ===========================================================================
# Test: main() calls reload_production after DONE result
# ===========================================================================


class TestMainReloadsAfterDone:
    """Verify that main() calls systemctl reload after a successful issue."""

    @patch("ralph.subprocess.run")
    def test_systemctl_reload_called_after_done(self, mock_run):
        """After opencode returns DONE, systemctl reload must be called."""
        mock_run.side_effect = _make_one_issue_side_effect(Results.DONE)

        main()

        # Find all systemctl reload calls
        systemctl_calls = [
            c
            for c in mock_run.call_args_list
            if len(c.args) > 0 and len(c.args[0]) >= 2 and c.args[0][0] == "systemctl" and c.args[0][1] == "reload"
        ]
        assert len(systemctl_calls) >= 1, (
            f"Expected at least one 'systemctl reload' call after DONE, got none. All calls: {mock_run.call_args_list}"
        )
        assert systemctl_calls[0].args[0] == [
            "systemctl",
            "reload",
            "just-ralph-it.service",
        ]

    @patch("ralph.subprocess.run")
    def test_systemctl_reload_called_after_opencode(self, mock_run):
        """systemctl reload must be called AFTER opencode finishes."""
        mock_run.side_effect = _make_one_issue_side_effect(Results.DONE)

        main()

        all_calls = mock_run.call_args_list

        opencode_indices = [i for i, c in enumerate(all_calls) if len(c.args) > 0 and c.args[0][0] == "opencode"]
        systemctl_indices = [i for i, c in enumerate(all_calls) if len(c.args) > 0 and c.args[0][0] == "systemctl"]

        assert len(opencode_indices) >= 1
        assert len(systemctl_indices) >= 1
        assert systemctl_indices[0] > opencode_indices[0], (
            f"'systemctl reload' (index {systemctl_indices[0]}) must come "
            f"AFTER 'opencode' (index {opencode_indices[0]})"
        )

    @patch("ralph.subprocess.run")
    def test_no_reload_on_human_needed(self, mock_run):
        """systemctl reload should NOT be called when result is HUMAN_NEEDED."""
        mock_run.side_effect = _make_one_issue_side_effect(Results.HUMAN_NEEDED)

        main()

        systemctl_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][0] == "systemctl"]
        assert len(systemctl_calls) == 0, (
            f"systemctl reload should NOT be called on HUMAN_NEEDED, but was called {len(systemctl_calls)} time(s)"
        )

    @patch("ralph.subprocess.run")
    def test_no_reload_on_new_blocker(self, mock_run):
        """systemctl reload should NOT be called when result is NEW_BLOCKER."""
        mock_run.side_effect = _make_one_issue_side_effect(Results.NEW_BLOCKER)

        main()

        systemctl_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][0] == "systemctl"]
        assert len(systemctl_calls) == 0, (
            f"systemctl reload should NOT be called on NEW_BLOCKER, but was called {len(systemctl_calls)} time(s)"
        )
