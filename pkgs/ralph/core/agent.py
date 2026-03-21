"""OpenCode agent wrapper for processing tasks."""

import logging
import queue as queue_mod
import shutil
import subprocess
import threading
import time
from collections.abc import Generator
from enum import StrEnum
from pathlib import Path
from xml.etree import ElementTree

import tasks

from ..config import AGENT_NAME
from .exceptions import BadAgentStatus

logger = logging.getLogger(__name__)

OPENCODE_CMD = shutil.which("opencode") or str(Path.home() / ".opencode" / "bin" / "opencode")


class AgentStatus(StrEnum):
    """Agent execution result values.

    These values are output by Ralph (the OpenCode agent) as XML status
    messages to indicate the result of processing a task.
    """

    IDLE = "HAVEN'T STARTED YET"
    WORKING = "STILL WORKING"
    DONE = "COMPLETED ASSIGNED ISSUE"
    HELP = "HUMAN HELP ABSOLUTELY NEEDED"
    BLOCKED = "FOUND NEW BLOCKER ISSUE"


class Agent:
    """Wraps OpenCode to process a task and track completion status.

    The agent runs OpenCode as a subprocess, streams its output, and parses
    the final status XML to determine if the task was completed, needs help,
    or discovered a blocking task.
    """

    def __init__(
        self,
        task: tasks.Task,
        model: str,
        i: int = 0,
        *args,
        tasks_cwd: Path | None = None,
        **kwargs,
    ) -> None:
        """Initialize the agent with a task to process.

        Args:
            task: The task to process
            model: OpenCode model to use (e.g., 'opencode/kimi-k2.5')
            i: Iteration index for logging
            *args: Additional arguments passed to OpenCode
            tasks_cwd: Working directory for task CRUD calls
            **kwargs: Additional keyword arguments passed to subprocess.Popen
        """
        self.status = AgentStatus.IDLE
        self.task = task
        self.i = i
        self._model = model
        self._args = args
        self._tasks_cwd = tasks_cwd
        self._kwargs = kwargs

    def claim_task(self) -> None:
        """Set task status to in_progress and assignee to ralph."""
        tasks.update_task(
            self.task.id,
            status=tasks.TaskStatus.IN_PROGRESS,
            assignee=AGENT_NAME,
            cwd=self._tasks_cwd,
        )

    def run(
        self, timeout: float | None = None, progress_timeout: float = 120.0
    ) -> Generator[str, None, None]:
        """Run OpenCode to process the task and stream output.

        Uses a threaded reader so we can detect both total timeout and
        progress stalls (no output for ``progress_timeout`` seconds).

        Args:
            timeout: Total timeout in seconds, kills process if exceeded.
            progress_timeout: Kill if no output for this many seconds.

        Yields:
            Lines of stdout from OpenCode.

        Raises:
            BadAgentStatus: If status XML is missing, unparseable, or unknown.
            subprocess.TimeoutExpired: If either timeout is exceeded.
        """
        if not shutil.which(OPENCODE_CMD):
            raise FileNotFoundError(
                f"'{OPENCODE_CMD}' not found on PATH. "
                f"Install OpenCode: https://opencode.ai/docs/installation"
            )

        self.status = AgentStatus.WORKING
        try:
            args = [
                OPENCODE_CMD,
                "run",
                self.task.as_xml(),
                "--model",
                self._model,
                "--agent",
                AGENT_NAME,
                "--title",
                self.task.title,
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
                    raise RuntimeError("No stdout from OpenCode, aborting")

                lines: list[str] = []
                start_time = time.monotonic()

                # Threaded reader: non-blocking so we can check timeouts
                q: queue_mod.Queue[str | None] = queue_mod.Queue()
                reader = threading.Thread(
                    target=self._read_stdout, args=(process.stdout, q), daemon=True
                )
                reader.start()

                last_output_time = start_time
                while True:
                    now = time.monotonic()
                    if timeout and (now - start_time) > timeout:
                        process.kill()
                        raise subprocess.TimeoutExpired(args, timeout)
                    try:
                        line = q.get(timeout=1.0)
                    except queue_mod.Empty:
                        if progress_timeout and (time.monotonic() - last_output_time) > progress_timeout:
                            process.kill()
                            raise subprocess.TimeoutExpired(args, progress_timeout)
                        continue
                    if line is None:  # EOF
                        break
                    last_output_time = time.monotonic()
                    lines.append(line)
                    yield line

                process.wait()

            self._parse_status(lines)
        finally:
            if self.status == AgentStatus.WORKING:
                self.status = AgentStatus.IDLE

    @staticmethod
    def _read_stdout(stdout, q: "queue_mod.Queue[str | None]") -> None:
        """Read stdout lines into a queue (runs in daemon thread)."""
        for line in stdout:
            q.put(line)
        q.put(None)

    def _parse_status(self, lines: list[str]) -> None:
        """Parse the agent's final status from the last non-empty line of output."""
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
            self.status = AgentStatus(status_msg)
        except ValueError:
            raise BadAgentStatus(f"Unknown status value: {status_msg!r}")
