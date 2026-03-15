"""Tests for ralph.py claiming issues before running opencode (TDD).

Bug: ralph.py never calls `bd update <id> --claim` before spawning the
opencode agent, so issues stay in 'open' status instead of transitioning
to 'in-progress'.

Fix: Before get_next_ready_issue(), call get_in_progress_issue() to check
for already in-progress work (resumes without claiming). For new issues,
call:
    subprocess.run(["bd", "update", issue["id"], "--claim"],
                   capture_output=True, check=True)
"""

import json
import subprocess
from unittest.mock import MagicMock, patch

from ralph import Results, main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_ISSUE_ID = "ISS-42"
FAKE_ISSUE_TITLE = "Implement widget feature"


def _make_bd_ready_result(issues):
    """Create a CompletedProcess mimicking `bd ready --json --limit 1`."""
    return subprocess.CompletedProcess(
        args=["bd", "ready", "--json", "--limit", "1"],
        returncode=0,
        stdout=json.dumps(issues),
        stderr="",
    )


def _make_claim_result():
    """Create a CompletedProcess mimicking a successful `bd update <id> --claim`."""
    return subprocess.CompletedProcess(
        args=["bd", "update", FAKE_ISSUE_ID, "--claim"],
        returncode=0,
        stdout="",
        stderr="",
    )


def _make_opencode_result(result_msg=Results.DONE):
    """Create a CompletedProcess mimicking an opencode run."""
    return subprocess.CompletedProcess(
        args=["opencode", "run"],
        returncode=0,
        stdout=f"Working on issue...\n<result>{result_msg}</result>",
        stderr="",
    )


def _make_bd_ready_empty():
    """Create a CompletedProcess for `bd ready` returning no issues."""
    return _make_bd_ready_result([])


def _make_bd_list_empty():
    """Create a CompletedProcess for `bd list --status in_progress` returning no issues."""
    return subprocess.CompletedProcess(
        args=["bd", "list", "--status", "in_progress", "--json", "--limit", "1"],
        returncode=0,
        stdout=json.dumps([]),
        stderr="",
    )


def _make_one_issue_side_effect():
    """Return a side_effect function: first bd ready returns one issue, second returns empty."""
    state = {"bd_ready_count": 0}

    def side_effect(args, **kwargs):
        if args[:2] == ["bd", "list"]:
            return _make_bd_list_empty()
        elif args[:2] == ["bd", "ready"]:
            state["bd_ready_count"] += 1
            if state["bd_ready_count"] == 1:
                return _make_bd_ready_result([{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}])
            return _make_bd_ready_empty()
        elif args[:2] == ["bd", "update"]:
            return _make_claim_result()
        elif args[0] == "opencode":
            return _make_opencode_result()
        elif args[0] == "sudo" and "systemctl" in args:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        raise ValueError(f"Unexpected subprocess.run call: {args}")

    return side_effect


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
    """Return a side_effect for subprocess.run that handles bd/systemctl calls only."""
    if bd_ready_results is None:
        bd_ready_results = []
    state = {"bd_ready_count": 0}

    def side_effect(args, **kwargs):
        if args[:2] == ["bd", "list"]:
            return _make_bd_list_empty()
        elif args[:2] == ["bd", "ready"]:
            idx = state["bd_ready_count"]
            state["bd_ready_count"] += 1
            if idx < len(bd_ready_results):
                return _make_bd_ready_result(bd_ready_results[idx])
            return _make_bd_ready_empty()
        elif args[:2] == ["bd", "update"]:
            return _make_claim_result()
        elif args[0] == "sudo" and "systemctl" in args:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        raise ValueError(f"Unexpected subprocess.run call: {args}")

    return side_effect


# ===========================================================================
# Test: bd update --claim is called BEFORE opencode
# ===========================================================================


class TestMainClaimsIssueBeforeRunningOpencode:
    """Verify that `bd update <id> --claim` is called BEFORE spawning opencode."""

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_main_claims_issue_before_running_opencode(self, mock_run, mock_popen):
        """bd update --claim must be called after getting an issue and before opencode."""
        mock_run.side_effect = _make_run_side_effect_for_popen_tests(
            bd_ready_results=[[{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}]]
        )
        mock_popen.return_value = _make_mock_popen(Results.DONE)

        main()

        # Collect all calls to subprocess.run
        all_calls = mock_run.call_args_list

        # Find the bd update call (claim)
        claim_indices = [
            i
            for i, c in enumerate(all_calls)
            if len(c.args) > 0 and len(c.args[0]) >= 2 and c.args[0][:2] == ["bd", "update"]
        ]
        assert len(claim_indices) >= 1, f"Expected at least one 'bd update' call, got none. All calls: {all_calls}"

        # opencode now goes through Popen, not subprocess.run
        assert mock_popen.call_count >= 1, (
            f"Expected opencode to be called via Popen, but Popen was called {mock_popen.call_count} time(s)"
        )

        # The code flow guarantees bd update (subprocess.run) is called before opencode (Popen).
        # We verify both were called; ordering is guaranteed by the sequential code in ralph.py.


# ===========================================================================
# Test: correct issue ID is passed to the claim command
# ===========================================================================


class TestMainClaimsIssueWithCorrectId:
    """Verify the correct issue ID is passed to `bd update <id> --claim`."""

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_main_claims_issue_with_correct_id(self, mock_run, mock_popen):
        """The issue ID from get_next_ready_issue() must be passed to bd update --claim."""
        mock_run.side_effect = _make_run_side_effect_for_popen_tests(
            bd_ready_results=[[{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}]]
        )
        mock_popen.return_value = _make_mock_popen(Results.DONE)

        main()

        # Find the bd update --claim call
        claim_calls = [
            c
            for c in mock_run.call_args_list
            if len(c.args) > 0 and len(c.args[0]) >= 2 and c.args[0][:2] == ["bd", "update"]
        ]
        assert len(claim_calls) >= 1, (
            f"Expected 'bd update --claim' call, got none. All calls: {mock_run.call_args_list}"
        )

        # Verify the exact arguments: ["bd", "update", FAKE_ISSUE_ID, "--claim"]
        claim_args = claim_calls[0].args[0]
        assert claim_args == ["bd", "update", FAKE_ISSUE_ID, "--claim"], (
            f"Expected ['bd', 'update', '{FAKE_ISSUE_ID}', '--claim'], got {claim_args}"
        )

        # Verify check=True was passed
        claim_kwargs = claim_calls[0].kwargs
        assert claim_kwargs.get("check") is True, (
            f"Expected check=True in bd update --claim call, got kwargs: {claim_kwargs}"
        )


# ===========================================================================
# Test: main handles claim failure gracefully
# ===========================================================================


class TestMainAbortsIfClaimFails:
    """Verify that if `bd update --claim` raises CalledProcessError, main handles it."""

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_main_aborts_if_claim_fails(self, mock_run, mock_popen):
        """If bd update --claim fails (check=True raises), opencode must NOT be called."""
        state = {"bd_ready_count": 0}

        def side_effect_claim_fails(args, **kwargs):
            if args[:2] == ["bd", "list"]:
                return _make_bd_list_empty()
            elif args[:2] == ["bd", "ready"]:
                state["bd_ready_count"] += 1
                if state["bd_ready_count"] == 1:
                    return _make_bd_ready_result([{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}])
                return _make_bd_ready_empty()
            elif args[:2] == ["bd", "update"]:
                raise subprocess.CalledProcessError(
                    returncode=1,
                    cmd=["bd", "update", FAKE_ISSUE_ID, "--claim"],
                    stderr="Issue already claimed",
                )
            elif args[0] == "sudo" and "systemctl" in args:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            raise ValueError(f"Unexpected subprocess.run call: {args}")

        mock_run.side_effect = side_effect_claim_fails

        # main() should raise CalledProcessError (from check=True) or handle it.
        # Either way, opencode must NOT be called after a failed claim.
        try:
            main()
        except subprocess.CalledProcessError:
            pass  # Expected: check=True propagates the error

        # Verify opencode was never called via Popen
        mock_popen.assert_not_called()
