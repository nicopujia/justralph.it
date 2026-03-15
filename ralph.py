import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

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


def main():
    setup_logging()
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

        issue = get_issue_by_id(args.issue) if args.issue else get_in_progress_issue() or get_next_ready_issue()

        if not issue:
            if args.issue:
                logger.error("Issue %s not found", args.issue)
            else:
                logger.info(Results.ALL_DONE)
            break

        subprocess.run(["bd", "update", issue["id"], "--status", "in_progress"], check=True)

        opencode_args = [
            "opencode",
            "run",
            get_prompt(issue["id"], "Human"),
            "--title",
            issue["title"],
            "--model",
            "anthropic/claude-opus-4-6",
        ]

        issue_id = issue["id"]
        iter_log_path = LOG_DIR / f"ralph_{issue_id}.log"
        iter_log_file = open(iter_log_path, "w")

        proc = subprocess.Popen(opencode_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
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
    )
    issues = json.loads(bd_result.stdout) if bd_result.stdout.strip() else []

    if not issues:
        return None

    return issues[0]


def get_next_ready_issue() -> dict[str, Any] | None:
    bd_result = subprocess.run(["bd", "ready", "--json", "--limit", "1"], capture_output=True, text=True)
    ready_issues = json.loads(bd_result.stdout) if bd_result.stdout.strip() else []

    if not ready_issues:
        return

    return ready_issues[0]


def get_issue_by_id(issue_id: str) -> dict[str, Any] | None:
    """Get a specific issue by its ID."""
    bd_result = subprocess.run(["bd", "show", issue_id, "--json"], capture_output=True, text=True)

    if bd_result.returncode != 0:
        return

    return json.loads(bd_result.stdout)[0] if bd_result.stdout.strip() else None


def get_prompt(issue_id: str, username: str) -> str:
    return f"""Complete {issue_id}. When you finish, {output(Results.DONE)}.

## KEEP IN MIND

- You have FULL ROOT and INTERNET ACCESS on this machine. Take advantage of it. Remind your subagents about it.
- While always matching the specs, (1) AVOID human help and (2) do the SIMPLEST thing that could possibly work.
- ALWAYS follow TDD principles.

### How to manage subagents

Tell them that:

- They might want to leave notes for future subagents if they figure useful things out. The notes must be AS CONCISE AS POSSIBLE, and written in `AGENTS.md` files in the corresponding directory, avoiding the root directory if possible.
- If they find out a *needed* fix or refactor, they should check — using a subagent — if there's already an issue for that. If there isn't already, they should file a new issue. If it's a blocker for {issue_id}, they must report back to you and you must {output(Results.NEW_BLOCKER)}. Otherwise, they MUST NOT report anything back whether they file the issue or not.
- If they're blocked because they ABSOLUTELY NEED human help (e.g. for real identity verification), they must think AGAIN and HARDER if they could *possibly* do it themselves. If they REALLY cannot, they should file a new issue. It must be assigned to `{username}` and specify what, how, and why needs to be done, and why the human help is *absolutely* necessary. Then, {output(Results.HUMAN_NEEDED)}.
- All subagents must run non-interactively. Never use commands that prompt for input. Always use non-interactive flags: `apt-get -y`, `cp -f`, `mv -f`, `rm -f`, `rm -rf`, `npm --yes`, etc. If a command requires interaction, fail fast and report back.

## CONSTRAINTS

- DO NOT work on ANYTHING ELSE other than {issue_id}.
- NEVER assume a feature or preference that isn't explicitly specified in the issue.
- Be an ORCHESTRATOR, not a worker. You must offload your work to subagents instead of doing it yourself. Whether for research, planning, coding, testing, or anything else, use AS MANY SUBAGENTS AS YOU NEED—which might even be hundreds of them. However, verify the final result using A SINGLE subagent after all the rest have finished working.
"""


def output(msg: str) -> str:
    return f"output `<result>{msg}</result>` in a new line and stop"


if __name__ == "__main__":
    main()
