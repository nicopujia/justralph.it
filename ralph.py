import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import psutil

from app.subprocess_env import subprocess_env

LOG_DIR = Path.home() / "projects" / "just-ralph-it" / "logs"
LOG_FILE = Path.home() / "projects" / "just-ralph-it" / "ralph.log"
STOP_FILE = Path.home() / "projects" / "just-ralph-it" / ".stop"

logger = logging.getLogger(__name__)


class Results:
    DONE = "COMPLETED ASSIGNED ISSUE"
    ALL_DONE = "NO MORE ISSUES LEFT"
    HUMAN_NEEDED = "I NEED A HUMAN"
    NEW_BLOCKER = "FOUND NEW BLOCKER ISSUE"
    STOPPED = "STOPPING AS REQUESTED"
    RESOURCES_EXHAUSTED = "STOPPING: VPS RESOURCES EXCEEDED"


def check_resources(threshold: float = 90.0) -> tuple[bool, str]:
    """Check RAM and disk usage; return (exceeded, message)."""
    ram_percent = psutil.virtual_memory().percent
    disk = shutil.disk_usage("/")
    disk_percent = disk.used / disk.total * 100

    exceeded = {}
    if ram_percent > threshold:
        exceeded["RAM"] = ram_percent
    if disk_percent > threshold:
        exceeded["disk"] = disk_percent

    if not exceeded:
        return False, ""

    # Report the resource with the highest usage
    resource, percent = max(exceeded.items(), key=lambda x: x[1])
    message = (
        f"Ralph stopped: VPS resources at {round(percent)}% {resource}. Free up space or upgrade before continuing."
    )
    return True, message


def main():
    setup_logging()

    # Record initial modification time for self-reload
    initial_mtime = os.path.getmtime(__file__)

    parser = argparse.ArgumentParser(description="Ralph Wiggum technique automation")
    parser.add_argument(
        "--one",
        action="store_true",
        help="Run only one iteration instead of looping until all issues are done",
    )
    parser.add_argument(
        "--issue",
        type=str,
        help="Specify a particular issue ID to work on (e.g., bd-42)",
    )
    args = parser.parse_args()

    while True:
        if STOP_FILE.exists():
            STOP_FILE.unlink()
            logger.info(Results.STOPPED)
            break

        # Check if ralph.py has been modified and reload if so
        current_mtime = os.path.getmtime(__file__)
        if current_mtime != initial_mtime:
            logger.info("ralph.py modified, reloading with updated code...")
            os.execv(sys.executable, [sys.executable] + sys.argv)

        resources_exceeded, resource_msg = check_resources()
        if resources_exceeded:
            logger.info(resource_msg)
            logger.info(Results.RESOURCES_EXHAUSTED)
            break

        issue = get_issue_by_id(args.issue) if args.issue else get_in_progress_issue() or get_next_ready_issue()

        if not issue:
            if args.issue:
                logger.error("Issue %s not found", args.issue)
            else:
                logger.info(Results.ALL_DONE)
            break

        subprocess.run(["bd", "update", issue["id"], "--status", "in_progress"], check=True, env=subprocess_env())

        opencode_args = [
            "opencode",
            "run",
            get_prompt(issue["id"], "Human"),
            "--title",
            issue["title"],
            "--model",
            "opencode/kimi-k2.5",
        ]

        issue_id = issue["id"]
        iter_log_path = LOG_DIR / f"ralph_{issue_id}.log"
        iter_log_file = open(iter_log_path, "w")

        proc = subprocess.Popen(
            opencode_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=subprocess_env()
        )
        assert proc.stdout is not None

        lines = []
        for line in proc.stdout:
            logger.info(line.rstrip())
            for handler in logging.getLogger().handlers:
                if isinstance(handler, logging.FileHandler):
                    handler.flush()
            iter_log_file.write(line)
            iter_log_file.flush()
            lines.append(line)
        proc.wait()
        iter_log_file.close()

        last_line = ""
        for line in reversed(lines):
            if line.strip():
                last_line = line.strip()
                break
        result_xml = last_line
        result_msg = ElementTree.fromstring(result_xml).text

        if result_msg == Results.DONE:
            reload_production()
            if args.one or args.issue:
                break
            continue
        elif result_msg == Results.HUMAN_NEEDED:
            break
        elif result_msg == Results.NEW_BLOCKER:
            break


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter("%(message)s"))

    file_handler = logging.FileHandler(LOG_FILE, mode="a")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(stdout_handler)
    root.addHandler(file_handler)


def reload_production():
    """Reload the production web server so code changes go live."""
    try:
        subprocess.run(
            ["sudo", "-n", "systemctl", "reload", "just-ralph-it.service"],
            check=True,
            capture_output=True,
            env=subprocess_env(),
        )
        logger.info("Production reloaded successfully.")
    except subprocess.CalledProcessError as e:
        logger.warning("Failed to reload production: %s", e.stderr)


def get_in_progress_issue() -> dict[str, Any] | None:
    """Check if there's already an in-progress issue and return it."""
    bd_result = subprocess.run(
        ["bd", "list", "--status", "in_progress", "--json", "--limit", "1"],
        capture_output=True,
        text=True,
        env=subprocess_env(),
    )
    issues = json.loads(bd_result.stdout) if bd_result.stdout.strip() else []

    if not issues:
        return None

    return issues[0]


def get_next_ready_issue() -> dict[str, Any] | None:
    bd_result = subprocess.run(
        ["bd", "ready", "--json", "--limit", "1"], capture_output=True, text=True, env=subprocess_env()
    )
    ready_issues = json.loads(bd_result.stdout) if bd_result.stdout.strip() else []

    if not ready_issues:
        return

    return ready_issues[0]


def get_issue_by_id(issue_id: str) -> dict[str, Any] | None:
    """Get a specific issue by its ID."""
    bd_result = subprocess.run(["bd", "show", issue_id, "--json"], capture_output=True, text=True, env=subprocess_env())

    if bd_result.returncode != 0:
        return

    return json.loads(bd_result.stdout)[0] if bd_result.stdout.strip() else None


def get_prompt(issue_id: str, username: str) -> str:
    return f"""Complete {issue_id}. When you finish, {output(Results.DONE)}.

## KEEP IN MIND

- You have FULL ROOT and INTERNET ACCESS on this machine. Take advantage of it. Remind your subagents about it.
- While always matching the specs, (1) AVOID human help and (2) do the SIMPLEST thing that could possibly work.
- ALWAYS follow TDD principles. Exception: documentation (README, AGENTS.md, comments, etc.), system prompts, opencode config, and other non-code text files do not need automated tests — but you must manually verify they are correct and complete after changes. Do not write automated tests to verify documentation content, prompt content, or config values.

### Documentation

When building a project, create or update a concise README.md covering: (1) prerequisites, (2) environment variables in .env, (3) how to run locally, (4) how to run tests, (5) how to deploy. No fluff — only what's necessary for a fresh clone to work. Manually verify the README is accurate and complete.

### After UI or integration changes

- Unit tests alone are NOT sufficient. You MUST also verify changes as a human would — in a real browser, in [production](https://justralph.it).
- Use the project's E2E test framework to simulate real user flows: click buttons, fill forms, navigate pages, and check what appears on screen.
- Verify the happy path works end-to-end before closing any UI or integration issue.
- Check for obvious visual or functional regressions.
- Do NOT close an issue until browser-level verification passes.

### How to manage subagents

Tell them that:

- They might want to leave notes for future subagents if they figure useful things out. The notes must be AS CONCISE AS POSSIBLE, and written in `AGENTS.md` files in the corresponding directory, avoiding the root directory if possible.
- If they find out a *needed* fix or refactor, they should check — using a subagent — if there's already an issue for that. If there isn't already, they should file a new issue. If it's a blocker for {issue_id}, they must report back to you and you must {output(Results.NEW_BLOCKER)}. Otherwise, they MUST NOT report anything back whether they file the issue or not.
- If they're blocked because they ABSOLUTELY NEED human help (e.g. for real identity verification), they must think AGAIN and HARDER if they could *possibly* do it themselves. If they REALLY cannot, they should file a new issue. It must be assigned to `{username}` and specify what, how, and why needs to be done, and why the human help is *absolutely* necessary. Then, {output(Results.HUMAN_NEEDED)}.
- All subagents must run non-interactively. Never use commands that prompt for input. Always use non-interactive flags: `apt-get -y`, `cp -f`, `mv -f`, `rm -f`, `rm -rf`, `npm --yes`, etc. If a command requires interaction, fail fast and report back.
- They should use subagents for each of their discrete tasks. Example: if they need to analyze 5 directories, they should use 5 subagents.

## CONSTRAINTS

- DO NOT work on ANYTHING ELSE other than {issue_id}.
- NEVER assume a feature or preference that isn't explicitly specified in the issue.
- Be an ORCHESTRATOR, not a worker. You must offload your work to subagents instead of doing it yourself. Whether for research, planning, coding, debugging, testing, or anything else, use up to 500 subagents. However, verify the final result using A SINGLE subagent after all the rest have finished working (such subagent may need sub-subagents, though).
"""


def output(msg: str) -> str:
    return f"output `<result>{msg}</result>` in a new line and stop"


if __name__ == "__main__":
    main()
