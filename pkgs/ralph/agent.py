import logging
import subprocess
import time
from collections.abc import Generator
from enum import Enum
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import bd

logger = logging.getLogger(__name__)


class Agent:
    class Status(Enum):
        IDLE = "HAVEN'T STARTED YET"
        WORKING = "STILL WORKING"
        DONE = "COMPLETED ASSIGNED ISSUE"
        HELP = "HUMAN HELP ABSOLUTELY NEEDED"
        BLOCKED = "FOUND NEW BLOCKER ISSUE"

    def __init__(
        self,
        issue: bd.Issue,
        model: str,
        prompt_file: Path,
        i: int = 0,
        *args,
        **kwargs,
    ) -> None:
        self.status = self.Status.IDLE
        self.issue = issue
        self.i = i
        self._model = model
        self._prompt_file = prompt_file
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
        """Yield OpenCode's stdout line by line and update status."""
        self.status = self.Status.WORKING
        try:
            prompt = self._prompt_file.read_text().format(self=self)
            args = ["opencode", "run", prompt, "--model", self._model, *self._args]
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
            raise BadRalphStatus("No output from OpenCode")

        try:
            status_msg = ElementTree.fromstring(status_xml).text
        except ElementTree.ParseError:
            raise BadRalphStatus(
                f"Failed to parse status XML from last line: {status_xml!r}",
            )

        try:
            self.status = self.Status(status_msg)
        except ValueError:
            raise BadRalphStatus(f"Unknown status value: {status_msg!r}")

    def __getattr__(self, name: str, /) -> Any:
        self.status = self.Status[name]
        return f"output `<Status>{self.status.value}</Status>` in a new line and stop"


class BadRalphStatus(ValueError):
    """Ralph didn't output or output a wrong status"""
