import json
import subprocess
from typing import Any
from xml.etree import ElementTree


class Results:
    DONE = "COMPLETED ASSIGNED ISSUE"
    ALL_DONE = "NO MORE ISSUES LEFT"
    HUMAN_NEEDED = "I NEED A HUMAN"
    NEW_BLOCKER = "FOUND NEW BLOCKER ISSUE"


def main():
    while True:
        issue = get_next_ready_issue()

        if not issue:
            print(Results.ALL_DONE)
            break

        args = [
            "opencode",
            "run",
            "--agent",
            "build",
            "--prompt",
            get_prompt(issue["id"], "human"),
            "--title",
            issue["title"],
            "--model",
            "anthropic/claude-opus-4-6",
        ]
        result = subprocess.run(args, capture_output=True, text=True)
        result_xml = result.stdout.split("\n")[-1].strip()
        result_msg = ElementTree.fromstring(result_xml).text

        print(result.stdout)

        if result_msg == Results.DONE:
            continue
        elif result_msg == Results.HUMAN_NEEDED:
            break
        elif result_msg == Results.NEW_BLOCKER:
            break


def get_next_ready_issue() -> dict[str, Any] | None:
    bd_result = subprocess.run(
        ["bd", "ready", "--json", "--limit", "1"], capture_output=True, text=True
    )
    ready_issues = json.loads(bd_result.stdout) if bd_result.stdout.strip() else []

    if not ready_issues:
        return

    return ready_issues[0]


def get_prompt(issue_id: str, username: str) -> str:
    return f"""Complete {issue_id}. When you finish, {output(Results.DONE)}.

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
