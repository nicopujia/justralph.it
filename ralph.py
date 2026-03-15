import argparse
import json
import subprocess
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

STOP_FILE = Path.home() / "projects" / "just-ralph-it" / ".stop"


class Results:
    DONE = "COMPLETED ASSIGNED ISSUE"
    ALL_DONE = "NO MORE ISSUES LEFT"
    HUMAN_NEEDED = "I NEED A HUMAN"
    NEW_BLOCKER = "FOUND NEW BLOCKER ISSUE"
    STOPPED = "Stopping as requested."


def main():
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
            print(Results.STOPPED)
            break

        if args.issue:
            issue = get_issue_by_id(args.issue)
        else:
            issue = get_next_ready_issue()

        if not issue:
            if args.issue:
                print(f"Error: Issue {args.issue} not found")
            else:
                print(Results.ALL_DONE)
            break

        opencode_args = [
            "opencode",
            "run",
            get_prompt(issue["id"], "human"),
            "--title",
            issue["title"],
            "--model",
            "anthropic/claude-opus-4-6",
        ]
        lines = []
        proc = subprocess.Popen(opencode_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="", flush=True)
            lines.append(line)
        proc.wait()

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


def reload_production():
    """Reload the production web server so code changes go live."""
    try:
        subprocess.run(
            ["systemctl", "reload", "just-ralph-it.service"],
            check=True,
            capture_output=True,
        )
        print("Production reloaded successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to reload production: {e.stderr}")


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
    return f"""Claim and complete {issue_id}. When you finish, {output(Results.DONE)}.

## KEEP IN MIND

- You have FULL ROOT and INTERNET ACCESS on this machine. Take advantage of it. Remind your subagents about it.
- While always matching the specs, (1) AVOID human help and (2) do the SIMPLEST thing that could possibly work.
- ALWAYS follow TDD principles.

### How to manage subagents

They may leave notes for future subagents if they figure useful things out. The notes must be AS CONCISE AS POSSIBLE, and written in `AGENTS.md` files in the corresponding directory, avoiding the root directory if possible.

If they find out a *needed* fix or refactor, they should check — using a subagent — if there's already an issue for that. If there isn't already, they should file a new issue. If it's a blocker for {issue_id}, they must report back to you and you must {output(Results.NEW_BLOCKER)}. Otherwise, they MUST NOT report anything back whether they file the issue or not.

If they're blocked because they ABSOLUTELY NEED human help (e.g. for real identity verification), they must think AGAIN and HARDER if they could *possibly* do it themselves. If they REALLY cannot, they should file a new issue. It must be assigned to `{username}` and specify what, how, and why needs to be done, and why the human help is *absolutely* necessary. Then, {output(Results.HUMAN_NEEDED)}.

## CONSTRAINTS

- DO NOT work on ANYTHING ELSE other than {issue_id}.
- NEVER assume a feature or preference that isn't explicitly specified in the issue.
- Be an ORCHESTRATOR, not a worker. You must offload your work to subagents instead of doing it yourself. Whether for research, planning, coding, testing, or anything else, use AS MANY SUBAGENTS AS YOU NEED—which might even be hundreds of them. However, verify the final result using A SINGLE subagent after all the rest have finished working.
"""


def output(msg: str) -> str:
    return f"output `<result>{msg}</result>` in a new line and stop"


if __name__ == "__main__":
    main()
