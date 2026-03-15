"""Tests for ralph.py claiming issues before running opencode (TDD).

Bug: ralph.py never calls `bd update <id> --claim` before spawning the
opencode agent, so issues stay in 'open' status instead of transitioning
to 'in-progress'.

Fix: After get_next_ready_issue() returns an issue and before spawning
the opencode subprocess, call:
    subprocess.run(["bd", "update", issue["id"], "--claim"], check=True)
"""

import json
import subprocess
from unittest.mock import patch

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


def _make_one_issue_side_effect():
    """Return a side_effect function: first bd ready returns one issue, second returns empty."""
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
            return _make_opencode_result()
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
    @patch("ralph.subprocess.run")
    def test_main_claims_issue_before_running_opencode(self, mock_run):
        """bd update --claim must be called after getting an issue and before opencode."""
        mock_run.side_effect = _make_one_issue_side_effect()

        main()

        # Collect all calls to subprocess.run
        all_calls = mock_run.call_args_list

        # Find the index of the bd update --claim call
        claim_indices = [
            i
            for i, c in enumerate(all_calls)
            if len(c.args) > 0 and len(c.args[0]) >= 2 and c.args[0][:2] == ["bd", "update"]
        ]
        assert len(claim_indices) >= 1, (
            f"Expected at least one 'bd update --claim' call, got none. All calls: {all_calls}"
        )

        # Find the index of the opencode call
        opencode_indices = [i for i, c in enumerate(all_calls) if len(c.args) > 0 and c.args[0][0] == "opencode"]
        assert len(opencode_indices) >= 1, f"Expected at least one 'opencode' call, got none. All calls: {all_calls}"

        # The claim call must come BEFORE the opencode call
        assert claim_indices[0] < opencode_indices[0], (
            f"'bd update --claim' (index {claim_indices[0]}) must be called "
            f"BEFORE 'opencode' (index {opencode_indices[0]}). "
            f"Call order: {[c.args[0][:2] for c in all_calls]}"
        )


# ===========================================================================
# Test: correct issue ID is passed to the claim command
# ===========================================================================


class TestMainClaimsIssueWithCorrectId:
    """Verify the correct issue ID is passed to `bd update <id> --claim`."""

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.run")
    def test_main_claims_issue_with_correct_id(self, mock_run):
        """The issue ID from get_next_ready_issue() must be passed to bd update --claim."""
        mock_run.side_effect = _make_one_issue_side_effect()

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


# ===========================================================================
# Test: main handles claim failure gracefully
# ===========================================================================


class TestMainAbortsIfClaimFails:
    """Verify that if `bd update --claim` raises CalledProcessError, main handles it."""

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.subprocess.run")
    def test_main_aborts_if_claim_fails(self, mock_run):
        """If bd update --claim fails (check=True raises), opencode must NOT be called."""
        state = {"bd_ready_count": 0}

        def side_effect_claim_fails(args, **kwargs):
            if args[:2] == ["bd", "ready"]:
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
            elif args[0] == "opencode":
                return _make_opencode_result()
            raise ValueError(f"Unexpected subprocess.run call: {args}")

        mock_run.side_effect = side_effect_claim_fails

        # main() should raise CalledProcessError (from check=True) or handle it.
        # Either way, opencode must NOT be called after a failed claim.
        try:
            main()
        except subprocess.CalledProcessError:
            pass  # Expected: check=True propagates the error

        # Verify opencode was never called
        opencode_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][0] == "opencode"]
        assert len(opencode_calls) == 0, (
            f"opencode should NOT be called when bd update --claim fails, "
            f"but it was called {len(opencode_calls)} time(s). "
            f"All calls: {mock_run.call_args_list}"
        )
