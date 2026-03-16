"""Tests for ralph.py per-iteration log files + main log.

Verifies:
- LOG_FILE points to the project root (not inside logs/)
- Each issue iteration creates a per-iteration log file in logs/
- Per-iteration log files follow the naming convention ralph_<issue_id>.log
- Both ralph.log and per-iteration logs receive opencode output
- ralph.log accumulates output across multiple issues
- Per-iteration logs are separate (each contains only its own issue's output)
- File handlers flush in real-time
"""

import json
import logging
import re
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import ralph
from ralph import Results, main

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAKE_ISSUE_1 = {"id": "bd-101", "title": "First issue"}
FAKE_ISSUE_2 = {"id": "bd-202", "title": "Second issue"}

OPENCODE_LINES_1 = [
    "Starting work on bd-101...\n",
    "Implementing feature alpha\n",
    f"<result>{Results.DONE}</result>\n",
]

OPENCODE_LINES_2 = [
    "Starting work on bd-202...\n",
    "Fixing bug beta\n",
    f"<result>{Results.DONE}</result>\n",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_popen(lines):
    """Create a mock Popen that yields the given lines from stdout."""
    mock_proc = MagicMock()
    mock_proc.stdout = iter(lines)
    mock_proc.wait.return_value = 0
    return mock_proc


def _make_run_side_effect(bd_ready_results):
    """Return a side_effect for subprocess.run that handles bd + systemctl calls.

    bd_ready_results: list of lists-of-issues for successive bd ready calls.
    """
    state = {"bd_ready_count": 0}

    def side_effect(args, **kwargs):
        if args[:2] == ["bd", "list"]:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout=json.dumps([]), stderr="")
        if args[:2] == ["bd", "ready"]:
            idx = state["bd_ready_count"]
            state["bd_ready_count"] += 1
            if idx < len(bd_ready_results):
                issues = bd_ready_results[idx]
            else:
                issues = []
            return subprocess.CompletedProcess(
                args=["bd", "ready", "--json", "--limit", "1"],
                returncode=0,
                stdout=json.dumps(issues),
                stderr="",
            )
        elif args[:2] == ["bd", "update"]:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        elif args[0] == "sudo" and "systemctl" in args:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        raise ValueError(f"Unexpected subprocess.run call: {args}")

    return side_effect


def _clear_logging():
    """Remove all handlers from root logger so each test starts fresh."""
    root = logging.getLogger()
    root.handlers.clear()


# ===========================================================================
# Test: LOG_FILE points to project root, not inside logs/
# ===========================================================================


class TestLogFilePath:
    """LOG_FILE should be at the project root, not inside logs/."""

    def test_log_file_at_project_root(self):
        """ralph.LOG_FILE should equal ~/projects/just-ralph-it/ralph.log."""
        expected = Path.home() / "projects" / "just-ralph-it" / "ralph.log"
        assert ralph.LOG_FILE == expected, f"LOG_FILE should be {expected}, got {ralph.LOG_FILE}"

    def test_log_file_not_inside_logs_dir(self):
        """ralph.LOG_FILE should NOT be inside the logs/ subdirectory."""
        assert ralph.LOG_DIR not in ralph.LOG_FILE.parents, (
            f"LOG_FILE ({ralph.LOG_FILE}) should not be inside LOG_DIR ({ralph.LOG_DIR})"
        )


# ===========================================================================
# Test: Per-iteration log file creation and naming
# ===========================================================================


class TestPerIterationLogCreation:
    """Each issue iteration should create a per-iteration log in logs/."""

    @patch("sys.argv", ["ralph.py", "--one"])
    @patch("ralph.STOP_FILE", MagicMock(exists=MagicMock(return_value=False)))
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_per_iteration_log_created(self, mock_run, mock_popen, tmp_path):
        """Processing an issue should create a log file matching
        ralph_<issue_id>.log in the logs directory."""
        _clear_logging()

        tmp_logs = tmp_path / "logs"
        tmp_main_log = tmp_path / "ralph.log"

        mock_run.side_effect = _make_run_side_effect(bd_ready_results=[[FAKE_ISSUE_1]])
        mock_popen.return_value = _make_mock_popen(OPENCODE_LINES_1)

        with (
            patch("ralph.LOG_DIR", tmp_logs),
            patch("ralph.LOG_FILE", tmp_main_log),
        ):
            main()

        # Find per-iteration log files
        log_files = list(tmp_logs.glob(f"ralph_{FAKE_ISSUE_1['id']}.log"))
        assert len(log_files) == 1, (
            f"Expected exactly 1 per-iteration log for {FAKE_ISSUE_1['id']}, "
            f"found {len(log_files)}: {[f.name for f in tmp_logs.glob('*')]}"
        )

    @patch("sys.argv", ["ralph.py", "--one"])
    @patch("ralph.STOP_FILE", MagicMock(exists=MagicMock(return_value=False)))
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_per_iteration_log_naming_convention(self, mock_run, mock_popen, tmp_path):
        """Per-iteration log should be named ralph_<issue_id>.log (e.g., ralph_bd-101.log)."""
        _clear_logging()

        tmp_logs = tmp_path / "logs"
        tmp_main_log = tmp_path / "ralph.log"

        mock_run.side_effect = _make_run_side_effect(bd_ready_results=[[FAKE_ISSUE_1]])
        mock_popen.return_value = _make_mock_popen(OPENCODE_LINES_1)

        with (
            patch("ralph.LOG_DIR", tmp_logs),
            patch("ralph.LOG_FILE", tmp_main_log),
        ):
            main()

        log_files = list(tmp_logs.glob(f"ralph_{FAKE_ISSUE_1['id']}.log"))
        assert len(log_files) == 1

        filename = log_files[0].name
        # Expect: ralph_<issue_id>.log
        pattern = r"^ralph_" + re.escape(FAKE_ISSUE_1["id"]) + r"\.log$"
        assert re.match(pattern, filename), (
            f"Log filename {filename!r} doesn't match expected pattern ralph_{FAKE_ISSUE_1['id']}.log"
        )

    @patch("sys.argv", ["ralph.py", "--one"])
    @patch("ralph.STOP_FILE", MagicMock(exists=MagicMock(return_value=False)))
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_logs_dir_created_if_missing(self, mock_run, mock_popen, tmp_path):
        """The logs/ directory should be created automatically if it doesn't exist."""
        _clear_logging()

        tmp_logs = tmp_path / "logs"  # does NOT exist yet
        tmp_main_log = tmp_path / "ralph.log"

        mock_run.side_effect = _make_run_side_effect(bd_ready_results=[[FAKE_ISSUE_1]])
        mock_popen.return_value = _make_mock_popen(OPENCODE_LINES_1)

        assert not tmp_logs.exists()

        with (
            patch("ralph.LOG_DIR", tmp_logs),
            patch("ralph.LOG_FILE", tmp_main_log),
        ):
            main()

        assert tmp_logs.exists(), "LOG_DIR should be created automatically"


# ===========================================================================
# Test: Both files get opencode output
# ===========================================================================


class TestBothFilesReceiveOutput:
    """opencode stdout lines should appear in both ralph.log and per-iteration log."""

    @patch("sys.argv", ["ralph.py", "--one"])
    @patch("ralph.STOP_FILE", MagicMock(exists=MagicMock(return_value=False)))
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_main_log_contains_opencode_output(self, mock_run, mock_popen, tmp_path):
        """ralph.log should contain the opencode output lines."""
        _clear_logging()

        tmp_logs = tmp_path / "logs"
        tmp_main_log = tmp_path / "ralph.log"

        mock_run.side_effect = _make_run_side_effect(bd_ready_results=[[FAKE_ISSUE_1]])
        mock_popen.return_value = _make_mock_popen(OPENCODE_LINES_1)

        with (
            patch("ralph.LOG_DIR", tmp_logs),
            patch("ralph.LOG_FILE", tmp_main_log),
        ):
            main()

        assert tmp_main_log.exists(), "ralph.log should exist after a run"
        content = tmp_main_log.read_text()
        assert "Starting work on bd-101" in content
        assert "Implementing feature alpha" in content

    @patch("sys.argv", ["ralph.py", "--one"])
    @patch("ralph.STOP_FILE", MagicMock(exists=MagicMock(return_value=False)))
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_per_iteration_log_contains_opencode_output(self, mock_run, mock_popen, tmp_path):
        """The per-iteration log should contain the opencode output lines."""
        _clear_logging()

        tmp_logs = tmp_path / "logs"
        tmp_main_log = tmp_path / "ralph.log"

        mock_run.side_effect = _make_run_side_effect(bd_ready_results=[[FAKE_ISSUE_1]])
        mock_popen.return_value = _make_mock_popen(OPENCODE_LINES_1)

        with (
            patch("ralph.LOG_DIR", tmp_logs),
            patch("ralph.LOG_FILE", tmp_main_log),
        ):
            main()

        log_files = list(tmp_logs.glob(f"ralph_{FAKE_ISSUE_1['id']}.log"))
        assert len(log_files) == 1, f"Expected 1 per-iteration log, found: {[f.name for f in tmp_logs.glob('*')]}"

        content = log_files[0].read_text()
        assert "Starting work on bd-101" in content
        assert "Implementing feature alpha" in content


# ===========================================================================
# Test: ralph.log accumulates across multiple issues
# ===========================================================================


class TestMainLogAccumulation:
    """ralph.log should accumulate output from all issues in a loop run."""

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.STOP_FILE", MagicMock(exists=MagicMock(return_value=False)))
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_ralph_log_contains_output_from_both_issues(self, mock_run, mock_popen, tmp_path):
        """After processing two issues, ralph.log should contain output from both."""
        _clear_logging()

        tmp_logs = tmp_path / "logs"
        tmp_main_log = tmp_path / "ralph.log"

        # First call returns issue 1, second returns issue 2, third returns empty
        mock_run.side_effect = _make_run_side_effect(bd_ready_results=[[FAKE_ISSUE_1], [FAKE_ISSUE_2]])

        # First Popen call returns lines for issue 1, second for issue 2
        mock_popen.side_effect = [
            _make_mock_popen(OPENCODE_LINES_1),
            _make_mock_popen(OPENCODE_LINES_2),
        ]

        with (
            patch("ralph.LOG_DIR", tmp_logs),
            patch("ralph.LOG_FILE", tmp_main_log),
        ):
            main()

        assert tmp_main_log.exists(), "ralph.log should exist"
        content = tmp_main_log.read_text()

        # Output from issue 1
        assert "Starting work on bd-101" in content, f"ralph.log missing output from issue 1. Content:\n{content}"
        assert "Implementing feature alpha" in content

        # Output from issue 2
        assert "Starting work on bd-202" in content, f"ralph.log missing output from issue 2. Content:\n{content}"
        assert "Fixing bug beta" in content

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.STOP_FILE", MagicMock(exists=MagicMock(return_value=False)))
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_ralph_log_uses_append_mode(self, mock_run, mock_popen, tmp_path):
        """ralph.log should use append mode, not truncate on each run.

        The main file handler should NOT be a RotatingFileHandler — it should
        be a plain FileHandler in append mode so output accumulates."""
        _clear_logging()

        tmp_logs = tmp_path / "logs"
        tmp_main_log = tmp_path / "ralph.log"

        # Pre-populate ralph.log with content from a "previous run"
        tmp_logs.mkdir(parents=True, exist_ok=True)
        tmp_main_log.write_text("PREVIOUS RUN OUTPUT\n")

        mock_run.side_effect = _make_run_side_effect(bd_ready_results=[[FAKE_ISSUE_1]])
        mock_popen.return_value = _make_mock_popen(OPENCODE_LINES_1)

        with (
            patch("ralph.LOG_DIR", tmp_logs),
            patch("ralph.LOG_FILE", tmp_main_log),
        ):
            main()

        content = tmp_main_log.read_text()
        assert "PREVIOUS RUN OUTPUT" in content, "ralph.log should preserve content from previous runs (append mode)"
        assert "Starting work on bd-101" in content, "ralph.log should also contain new output"


# ===========================================================================
# Test: Per-iteration logs are separate
# ===========================================================================


class TestPerIterationLogSeparation:
    """Each issue should get its own per-iteration log with only its output."""

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.STOP_FILE", MagicMock(exists=MagicMock(return_value=False)))
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_each_issue_gets_separate_log(self, mock_run, mock_popen, tmp_path):
        """Two issues should produce two separate per-iteration log files."""
        _clear_logging()

        tmp_logs = tmp_path / "logs"
        tmp_main_log = tmp_path / "ralph.log"

        mock_run.side_effect = _make_run_side_effect(bd_ready_results=[[FAKE_ISSUE_1], [FAKE_ISSUE_2]])
        mock_popen.side_effect = [
            _make_mock_popen(OPENCODE_LINES_1),
            _make_mock_popen(OPENCODE_LINES_2),
        ]

        with (
            patch("ralph.LOG_DIR", tmp_logs),
            patch("ralph.LOG_FILE", tmp_main_log),
        ):
            main()

        logs_issue_1 = list(tmp_logs.glob(f"ralph_{FAKE_ISSUE_1['id']}.log"))
        logs_issue_2 = list(tmp_logs.glob(f"ralph_{FAKE_ISSUE_2['id']}.log"))

        assert len(logs_issue_1) == 1, (
            f"Expected 1 log for {FAKE_ISSUE_1['id']}, "
            f"found {len(logs_issue_1)}: {[f.name for f in tmp_logs.glob('*')]}"
        )
        assert len(logs_issue_2) == 1, (
            f"Expected 1 log for {FAKE_ISSUE_2['id']}, "
            f"found {len(logs_issue_2)}: {[f.name for f in tmp_logs.glob('*')]}"
        )

    @patch("sys.argv", ["ralph.py"])
    @patch("ralph.STOP_FILE", MagicMock(exists=MagicMock(return_value=False)))
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_per_iteration_log_contains_only_own_output(self, mock_run, mock_popen, tmp_path):
        """Each per-iteration log should contain only its own issue's output,
        not output from other issues."""
        _clear_logging()

        tmp_logs = tmp_path / "logs"
        tmp_main_log = tmp_path / "ralph.log"

        mock_run.side_effect = _make_run_side_effect(bd_ready_results=[[FAKE_ISSUE_1], [FAKE_ISSUE_2]])
        mock_popen.side_effect = [
            _make_mock_popen(OPENCODE_LINES_1),
            _make_mock_popen(OPENCODE_LINES_2),
        ]

        with (
            patch("ralph.LOG_DIR", tmp_logs),
            patch("ralph.LOG_FILE", tmp_main_log),
        ):
            main()

        # Issue 1's log should have its output but NOT issue 2's
        log_1 = list(tmp_logs.glob(f"ralph_{FAKE_ISSUE_1['id']}.log"))[0]
        content_1 = log_1.read_text()
        assert "Starting work on bd-101" in content_1
        assert "Implementing feature alpha" in content_1
        assert "Starting work on bd-202" not in content_1, "Issue 1's log should not contain issue 2's output"
        assert "Fixing bug beta" not in content_1, "Issue 1's log should not contain issue 2's output"

        # Issue 2's log should have its output but NOT issue 1's
        log_2 = list(tmp_logs.glob(f"ralph_{FAKE_ISSUE_2['id']}.log"))[0]
        content_2 = log_2.read_text()
        assert "Starting work on bd-202" in content_2
        assert "Fixing bug beta" in content_2
        assert "Starting work on bd-101" not in content_2, "Issue 2's log should not contain issue 1's output"
        assert "Implementing feature alpha" not in content_2, "Issue 2's log should not contain issue 1's output"


# ===========================================================================
# Test: Real-time flushing
# ===========================================================================


class TestRealTimeFlushing:
    """File handlers should flush after each write for real-time streaming."""

    @patch("sys.argv", ["ralph.py", "--one"])
    @patch("ralph.STOP_FILE", MagicMock(exists=MagicMock(return_value=False)))
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_main_log_handler_not_rotating(self, mock_run, mock_popen, tmp_path):
        """The main ralph.log handler should be a plain FileHandler, not
        RotatingFileHandler, to ensure simple append-mode accumulation."""
        _clear_logging()

        tmp_logs = tmp_path / "logs"
        tmp_main_log = tmp_path / "ralph.log"

        mock_run.side_effect = _make_run_side_effect(bd_ready_results=[[FAKE_ISSUE_1]])
        mock_popen.return_value = _make_mock_popen(OPENCODE_LINES_1)

        with (
            patch("ralph.LOG_DIR", tmp_logs),
            patch("ralph.LOG_FILE", tmp_main_log),
        ):
            main()

        root = logging.getLogger()
        file_handlers = [
            h for h in root.handlers if isinstance(h, logging.FileHandler) and Path(h.baseFilename) == tmp_main_log
        ]
        assert len(file_handlers) >= 1, "Expected a FileHandler for ralph.log"

        from logging.handlers import RotatingFileHandler

        for fh in file_handlers:
            assert not isinstance(fh, RotatingFileHandler), (
                "ralph.log handler should be a plain FileHandler, not RotatingFileHandler"
            )

    @patch("sys.argv", ["ralph.py", "--one"])
    @patch("ralph.STOP_FILE", MagicMock(exists=MagicMock(return_value=False)))
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_main_log_file_flushed_after_each_line(self, mock_run, mock_popen, tmp_path):
        """ralph.log should be readable with current content after each line is logged,
        not only after the process ends. We verify this by checking that the file
        has content after processing (as a proxy for real-time flushing)."""
        _clear_logging()

        tmp_logs = tmp_path / "logs"
        tmp_main_log = tmp_path / "ralph.log"

        lines_seen_during_write = []

        original_popen_lines = list(OPENCODE_LINES_1)

        class FlushCheckingPopen:
            """A mock Popen that checks ralph.log after each line is yielded."""

            def __init__(self, *args, **kwargs):
                self._lines = iter(original_popen_lines)
                self.returncode = 0

            @property
            def stdout(self):
                return self._line_generator()

            def _line_generator(self):
                for line in self._lines:
                    yield line
                    # After yielding a line and the caller processes it,
                    # check if ralph.log has been flushed
                    if tmp_main_log.exists():
                        lines_seen_during_write.append(tmp_main_log.read_text())

            def wait(self):
                return 0

        mock_run.side_effect = _make_run_side_effect(bd_ready_results=[[FAKE_ISSUE_1]])
        mock_popen.side_effect = lambda *a, **kw: FlushCheckingPopen(*a, **kw)

        with (
            patch("ralph.LOG_DIR", tmp_logs),
            patch("ralph.LOG_FILE", tmp_main_log),
        ):
            main()

        # After processing, the log should have content
        assert tmp_main_log.exists(), "ralph.log should exist"
        final_content = tmp_main_log.read_text()
        assert len(final_content) > 0, "ralph.log should not be empty"

        # For real-time flushing, content should be visible during iteration,
        # not only after the process ends. At least one intermediate check
        # should have seen content.
        assert len(lines_seen_during_write) > 0, (
            "ralph.log should be flushed during iteration (real-time), not only after the run completes"
        )
        # The first check (after first line is processed) should already have content
        assert len(lines_seen_during_write[0]) > 0, (
            "ralph.log should contain data after the very first line is logged (flush=True / real-time flushing)"
        )

    @patch("sys.argv", ["ralph.py", "--one"])
    @patch("ralph.STOP_FILE", MagicMock(exists=MagicMock(return_value=False)))
    @patch("ralph.subprocess.Popen")
    @patch("ralph.subprocess.run")
    def test_per_iteration_log_flushed_during_iteration(self, mock_run, mock_popen, tmp_path):
        """The per-iteration log should also be flushed in real-time."""
        _clear_logging()

        tmp_logs = tmp_path / "logs"
        tmp_main_log = tmp_path / "ralph.log"

        per_iter_content_during_write = []
        original_popen_lines = list(OPENCODE_LINES_1)

        class FlushCheckingPopen:
            """A mock Popen that checks per-iteration log after each line."""

            def __init__(self, *args, **kwargs):
                self._lines = iter(original_popen_lines)
                self.returncode = 0

            @property
            def stdout(self):
                return self._line_generator()

            def _line_generator(self):
                for line in self._lines:
                    yield line
                    # Check per-iteration log after each line
                    iter_logs = list(tmp_logs.glob(f"ralph_{FAKE_ISSUE_1['id']}.log"))
                    if iter_logs:
                        per_iter_content_during_write.append(iter_logs[0].read_text())

            def wait(self):
                return 0

        mock_run.side_effect = _make_run_side_effect(bd_ready_results=[[FAKE_ISSUE_1]])
        mock_popen.side_effect = lambda *a, **kw: FlushCheckingPopen(*a, **kw)

        with (
            patch("ralph.LOG_DIR", tmp_logs),
            patch("ralph.LOG_FILE", tmp_main_log),
        ):
            main()

        # The per-iteration log should have been visible during the iteration
        assert len(per_iter_content_during_write) > 0, (
            "Per-iteration log should be flushed during iteration (real-time)"
        )
        assert len(per_iter_content_during_write[0]) > 0, (
            "Per-iteration log should have content after the first line is processed"
        )
