"""Tests for ralph.py logging output format.

The stdout handler should emit bare messages (no timestamp, no level prefix)
so that _watch_ralph() in app/routes.py and app/recovery.py can match
last_line against Results constants like "NO MORE ISSUES LEFT".

The file handler should keep the full format with timestamps for debugging.
"""

import logging
import io

from ralph import Results, setup_logging


class TestStdoutHandlerFormat:
    """stdout handler should use message-only format: %(message)s."""

    def _capture_stdout_output(self, log_method, message):
        """Call setup_logging(), replace the stdout handler's stream with a
        StringIO, log *message* via *log_method*, and return the captured text."""
        # Clear any existing handlers on the root logger so setup_logging()
        # starts fresh each test.
        root = logging.getLogger()
        root.handlers.clear()

        setup_logging()

        # Find the StreamHandler (stdout handler) among root handlers
        stream_handler = None
        for h in root.handlers:
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
                stream_handler = h
                break
        assert stream_handler is not None, "No StreamHandler found on root logger"

        # Replace its stream with a StringIO to capture output
        buf = io.StringIO()
        stream_handler.stream = buf

        log_method(message)

        return buf.getvalue()

    def test_all_done_message_is_bare(self):
        """logger.info(Results.ALL_DONE) should produce exactly
        'NO MORE ISSUES LEFT\\n' on stdout — no timestamp, no level."""
        logger = logging.getLogger("ralph")
        output = self._capture_stdout_output(logger.info, Results.ALL_DONE)
        assert output.strip() == Results.ALL_DONE, f"Expected bare message {Results.ALL_DONE!r}, got {output.strip()!r}"

    def test_stopped_message_is_bare(self):
        """logger.info(Results.STOPPED) should produce exactly
        'Stopping as requested.\\n' on stdout — no timestamp, no level."""
        logger = logging.getLogger("ralph")
        output = self._capture_stdout_output(logger.info, Results.STOPPED)
        assert output.strip() == Results.STOPPED, f"Expected bare message {Results.STOPPED!r}, got {output.strip()!r}"

    def test_stdout_has_no_timestamp(self):
        """The stdout line should not contain a timestamp pattern."""
        import re

        logger = logging.getLogger("ralph")
        output = self._capture_stdout_output(logger.info, "test message")
        # A timestamp would look like 2026-03-15 10:30:00
        assert not re.search(r"\d{4}-\d{2}-\d{2}", output), (
            f"stdout output should not contain a timestamp, got {output!r}"
        )

    def test_stdout_has_no_level_prefix(self):
        """The stdout line should not contain 'INFO', 'WARNING', etc."""
        logger = logging.getLogger("ralph")
        output = self._capture_stdout_output(logger.info, "test message")
        assert "INFO" not in output, f"stdout output should not contain level prefix, got {output!r}"


class TestFileHandlerFormat:
    """file handler should keep full format: %(asctime)s %(levelname)s %(message)s."""

    def test_file_handler_has_timestamp_format(self):
        """The file handler's formatter should include asctime and levelname."""
        root = logging.getLogger()
        root.handlers.clear()

        setup_logging()

        # Find the FileHandler
        file_handler = None
        for h in root.handlers:
            if isinstance(h, logging.FileHandler):
                file_handler = h
                break
        assert file_handler is not None, "No FileHandler found on root logger"

        fmt_str = file_handler.formatter._fmt
        assert "asctime" in fmt_str, f"File handler format should include asctime, got {fmt_str!r}"
        assert "levelname" in fmt_str, f"File handler format should include levelname, got {fmt_str!r}"
