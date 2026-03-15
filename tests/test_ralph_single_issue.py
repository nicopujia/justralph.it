"""Tests for ralph.py single-issue enforcement (TDD — written before implementation).

Bug: Ralph can claim and work on multiple issues simultaneously because:
1. It never checks for already in-progress issues before claiming a new one
2. It uses `bd update <id> -s in_progress` instead of `bd update <id> --claim`
3. It doesn't use `check=True` so claim failures are silently ignored

Fix:
1. Add get_in_progress_issue() that runs `bd list --status in_progress --json --limit 1`
2. In main(), before get_next_ready_issue(), check for in-progress issues and resume them
3. Change claim command to `bd update <id> --claim` with `check=True`
"""

import json
import subprocess
from unittest.mock import MagicMock, call, patch

from ralph import Results, main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_ISSUE_ID = "ISS-77"
FAKE_ISSUE_TITLE = "Single issue enforcement"

IN_PROGRESS_ISSUE = {"id": "ISS-50", "title": "Already in progress"}


def _make_bd_list_in_progress_result(issues):
    """Create a CompletedProcess mimicking `bd list --status in_progress --json --limit 1`."""
    return subprocess.CompletedProcess(
        args=["bd", "list", "--status", "in_progress", "--json", "--limit", "1"],
        returncode=0,
        stdout=json.dumps(issues),
        stderr="",
    )


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


def _make_claim_result(issue_id=FAKE_ISSUE_ID):
    return subprocess.CompletedProcess(
        args=["bd", "update", issue_id, "--claim"],
        returncode=0,
        stdout="",
        stderr="",
    )


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


# ===========================================================================
# Test: get_in_progress_issue()
# ===========================================================================


class TestGetInProgressIssue:
    """Tests for the new get_in_progress_issue() function."""

    @patch("ralph.subprocess.run")
    def test_returns_issue_when_one_in_progress(self, mock_run):
        """When bd list returns an in-progress issue, the function returns it."""
        from ralph import get_in_progress_issue

        mock_run.return_value = _make_bd_list_in_progress_result([IN_PROGRESS_ISSUE])

        result = get_in_progress_issue()

        mock_run.assert_called_once()
        call_args, call_kwargs = mock_run.call_args
        assert call_args == (["bd", "list", "--status", "in_progress", "--json", "--limit", "1"],)
        assert call_kwargs["capture_output"] is True
        assert call_kwargs["text"] is True
        assert result == IN_PROGRESS_ISSUE

    @patch("ralph.subprocess.run")
    def test_returns_none_when_no_in_progress(self, mock_run):
        """When bd list returns empty, function returns None."""
        from ralph import get_in_progress_issue

        mock_run.return_value = _make_bd_list_in_progress_result([])

        result = get_in_progress_issue()

        mock_run.assert_called_once()
        call_args, call_kwargs = mock_run.call_args
        assert call_args == (["bd", "list", "--status", "in_progress", "--json", "--limit", "1"],)
        assert call_kwargs["capture_output"] is True
        assert call_kwargs["text"] is True
        assert result is None


# ===========================================================================
# Test: main() resumes in-progress issue instead of claiming a new one
# ===========================================================================


class TestMainResumesInProgressIssue:
    """Tests that main() resumes an in-progress issue instead of claiming a new one."""

    @patch("sys.argv", ["ralph.py", "--one"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_resumes_in_progress_issue_instead_of_getting_ready(self, mock_run, mock_popen):
        """When there's an in-progress issue, main() works on it WITHOUT calling
        `bd ready` and WITHOUT calling `bd update --claim`."""

        def side_effect(args, **kwargs):
            if args[:2] == ["bd", "list"]:
                # bd list --status in_progress returns a result
                return _make_bd_list_in_progress_result([IN_PROGRESS_ISSUE])
            elif args[:2] == ["bd", "update"]:
                return _make_claim_result(IN_PROGRESS_ISSUE["id"])
            elif args[0] == "sudo" and "systemctl" in args:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            raise ValueError(f"Unexpected subprocess.run call: {args}")

        mock_run.side_effect = side_effect
        mock_popen.return_value = _make_mock_popen(Results.DONE)

        main()

        # Verify opencode was called (issue was worked on)
        assert mock_popen.call_count >= 1, "Expected opencode to be called for in-progress issue"

        # Verify opencode was called with the in-progress issue's title
        popen_call_args = mock_popen.call_args[0][0]
        assert IN_PROGRESS_ISSUE["title"] in popen_call_args, (
            f"Expected opencode to be called with in-progress issue title "
            f"'{IN_PROGRESS_ISSUE['title']}', got args: {popen_call_args}"
        )

        # Verify bd ready was NEVER called (we resumed instead)
        bd_ready_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][:2] == ["bd", "ready"]]
        assert len(bd_ready_calls) == 0, (
            f"bd ready should NOT be called when there's an in-progress issue, "
            f"but was called {len(bd_ready_calls)} time(s)"
        )

        # Verify bd update --claim was NEVER called (already in progress, no need to claim)
        bd_claim_calls = [
            c
            for c in mock_run.call_args_list
            if len(c.args) > 0 and c.args[0][:2] == ["bd", "update"] and "--claim" in c.args[0]
        ]
        assert len(bd_claim_calls) == 0, (
            f"bd update --claim should NOT be called for an already in-progress issue, "
            f"but was called {len(bd_claim_calls)} time(s)"
        )

    @patch("sys.argv", ["ralph.py", "--one"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_claims_new_issue_when_none_in_progress(self, mock_run, mock_popen):
        """When no in-progress issue exists, main() proceeds to `bd ready` and claims with --claim."""

        def side_effect(args, **kwargs):
            if args[:2] == ["bd", "list"]:
                # No in-progress issues
                return _make_bd_list_in_progress_result([])
            elif args[:2] == ["bd", "ready"]:
                return _make_bd_ready_result([{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}])
            elif args[:2] == ["bd", "update"]:
                # Must be called with --claim and check=True
                if kwargs.get("check") is not True:
                    raise AssertionError("bd update --claim must be called with check=True")
                return _make_claim_result(FAKE_ISSUE_ID)
            elif args[0] == "sudo" and "systemctl" in args:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            raise ValueError(f"Unexpected subprocess.run call: {args}")

        mock_run.side_effect = side_effect
        mock_popen.return_value = _make_mock_popen(Results.DONE)

        main()

        # Verify bd list was called (to check for in-progress)
        bd_list_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][:2] == ["bd", "list"]]
        assert len(bd_list_calls) >= 1, "Expected bd list to be called to check for in-progress issues"

        # Verify bd ready was called (no in-progress issue, so fetch next ready)
        bd_ready_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][:2] == ["bd", "ready"]]
        assert len(bd_ready_calls) >= 1, "Expected bd ready to be called when no in-progress issues"

        # Verify bd update --claim was called
        bd_claim_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][:2] == ["bd", "update"]]
        assert len(bd_claim_calls) >= 1, "Expected bd update --claim to be called"
        claim_args = bd_claim_calls[0].args[0]
        assert claim_args == ["bd", "update", FAKE_ISSUE_ID, "--claim"], (
            f"Expected ['bd', 'update', '{FAKE_ISSUE_ID}', '--claim'], got {claim_args}"
        )

        # Verify opencode was called
        assert mock_popen.call_count >= 1, "Expected opencode to be called for the claimed issue"


# ===========================================================================
# Test: main() uses atomic claim (--claim with check=True)
# ===========================================================================


class TestMainUsesAtomicClaim:
    """Tests that `bd update --claim` is used with `check=True`."""

    @patch("sys.argv", ["ralph.py", "--one"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_claim_uses_atomic_flag(self, mock_run, mock_popen):
        """Verify the command uses --claim not -s in_progress."""

        def side_effect(args, **kwargs):
            if args[:2] == ["bd", "list"]:
                return _make_bd_list_in_progress_result([])
            elif args[:2] == ["bd", "ready"]:
                return _make_bd_ready_result([{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}])
            elif args[:2] == ["bd", "update"]:
                return _make_claim_result(FAKE_ISSUE_ID)
            elif args[0] == "sudo" and "systemctl" in args:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            raise ValueError(f"Unexpected subprocess.run call: {args}")

        mock_run.side_effect = side_effect
        mock_popen.return_value = _make_mock_popen(Results.DONE)

        main()

        # Find the bd update call
        bd_update_calls = [c for c in mock_run.call_args_list if len(c.args) > 0 and c.args[0][:2] == ["bd", "update"]]
        assert len(bd_update_calls) >= 1, (
            f"Expected at least one 'bd update' call, got none. All calls: {mock_run.call_args_list}"
        )

        claim_args = bd_update_calls[0].args[0]

        # Must use --claim, not -s in_progress
        assert "--claim" in claim_args, f"Expected '--claim' in bd update args, got {claim_args}"
        assert "-s" not in claim_args, f"Expected '-s' NOT in bd update args (should use --claim), got {claim_args}"
        assert "in_progress" not in claim_args, (
            f"Expected 'in_progress' NOT in bd update args (should use --claim), got {claim_args}"
        )

        # Must be called with check=True
        claim_kwargs = bd_update_calls[0].kwargs
        assert claim_kwargs.get("check") is True, (
            f"Expected bd update --claim to be called with check=True, got kwargs: {claim_kwargs}"
        )

    @patch("sys.argv", ["ralph.py", "--one"])
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_claim_failure_prevents_opencode(self, mock_run, mock_popen):
        """If --claim raises CalledProcessError, opencode is NOT spawned."""

        def side_effect(args, **kwargs):
            if args[:2] == ["bd", "list"]:
                return _make_bd_list_in_progress_result([])
            elif args[:2] == ["bd", "ready"]:
                return _make_bd_ready_result([{"id": FAKE_ISSUE_ID, "title": FAKE_ISSUE_TITLE}])
            elif args[:2] == ["bd", "update"]:
                raise subprocess.CalledProcessError(
                    returncode=1,
                    cmd=["bd", "update", FAKE_ISSUE_ID, "--claim"],
                    stderr="Issue already claimed by another agent",
                )
            elif args[0] == "sudo" and "systemctl" in args:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            raise ValueError(f"Unexpected subprocess.run call: {args}")

        mock_run.side_effect = side_effect

        # main() should raise CalledProcessError (from check=True) or handle it gracefully.
        # Either way, opencode must NOT be called after a failed claim.
        try:
            main()
        except subprocess.CalledProcessError:
            pass  # Expected: check=True propagates the error

        # Verify opencode was never called via Popen
        mock_popen.assert_not_called()
