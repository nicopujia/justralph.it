"""OpenCode agent wrapper for processing Beads issues."""

import logging
import subprocess
import time
from collections.abc import Generator
from enum import Enum
from xml.etree import ElementTree

import bd

from .exceptions import BadAgentStatus

logger = logging.getLogger(__name__)


class Agent:
    """Wraps OpenCode to process a Beads issue and track completion status.

    The agent runs OpenCode as a subprocess, streams its output, and parses
    the final status XML to determine if the issue was completed, needs help,
    or discovered a blocking issue.
    """

    class Status(Enum):
        """Agent execution status values.

        These values are output by Ralph (the OpenCode agent) as XML status
        messages to indicate the result of processing an issue.
        """

        IDLE = "HAVEN'T STARTED YET"
        WORKING = "STILL WORKING"
        DONE = "COMPLETED ASSIGNED ISSUE"
        HELP = "HUMAN HELP ABSOLUTELY NEEDED"
        BLOCKED = "FOUND NEW BLOCKER ISSUE"

    def __init__(
        self,
        issue: bd.Issue,
        model: str,
        i: int = 0,
        *args,
        **kwargs,
    ) -> None:
        """Initialize the agent with an issue to process.

        Args:
            issue: The Beads issue to process
            model: OpenCode model to use (e.g., 'opencode/kimi-k2.5')
            i: Iteration index for logging
            *args: Additional arguments passed to OpenCode
            **kwargs: Additional keyword arguments passed to subprocess.Popen
        """
        self.status = self.Status.IDLE
        self.issue = issue
        self.i = i
        self._model = model
        self._args = args
        self._kwargs = kwargs

    def claim_issue(self) -> None:
        """Set issue status to in_progress and assignee to ralph."""
        bd.update_issue(
            self.issue.id,
            status="in_progress",
            assignee="ralph",
        )

    def run(self, timeout: float | None = None) -> Generator[str, None, None]:
        """Run OpenCode to process the issue and stream output.

        Executes OpenCode as a subprocess, yields each line of output, then
        parses the final status XML to determine completion state.

        Args:
            timeout: Optional timeout in seconds, kills process if exceeded

        Yields:
            Lines of stdout from OpenCode

        Raises:
            BadAgentStatus: If status XML is missing, unparseable, or unknown
            subprocess.TimeoutExpired: If timeout is exceeded
        """
        self.status = self.Status.WORKING
        try:
            args = [
                "opencode",
                "run",
                self.issue.as_xml(),
                "--model",
                self._model,
                "--agent",
                "ralph",
                "--title",
                self.issue.title,
                *self._args,
            ]
            logger.debug("Agent args: %s", args)

            with subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                **self._kwargs,
            ) as process:
                if not process.stdout:
                    raise Exception("No stdout from OpenCode, aborting")

                lines: list[str] = []
                start_time = time.monotonic()
                for line in process.stdout:
                    if timeout and (time.monotonic() - start_time) > timeout:
                        process.kill()
                        raise subprocess.TimeoutExpired(args, timeout)
                    lines.append(line)
                    yield line

                process.wait()
        finally:
            self.status = self.Status.IDLE

        status_xml = ""
        for line in reversed(lines):
            if line.strip():
                status_xml = line.strip()
                break

        if not status_xml:
            raise BadAgentStatus("No output from OpenCode")

        try:
            status_msg = ElementTree.fromstring(status_xml).text
        except ElementTree.ParseError:
            raise BadAgentStatus(
                f"Failed to parse status XML from last line: {status_xml!r}",
            )

        try:
            self.status = self.Status(status_msg)
        except ValueError:
            raise BadAgentStatus(f"Unknown status value: {status_msg!r}")

