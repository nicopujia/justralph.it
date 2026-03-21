# Path A: Ralphy -> Ralph Loop Integration Decisions

Date: 2026-03-20

## A1. Issue Creation (No PRD)

**Decision:** There is no PRD document. Ralphy creates `bd` issues directly via `bd create`.

- There is no intermediate PRD file (no MD, no document)
- What was previously called "PRD" is simply the set of `bd` issues themselves
- Ralphy's job: ask questions, extract intent, create well-formed `bd` issues
- Ralph Loop is a pure consumer -- it only calls `bd ready --json` per iteration
- The user never interacts with a PRD -- they interact with Ralphy (chatbot) and see issues in the UI

## A2. Data Formats

**Decision:** XML for agent prompts. Issues are the only data structure.

The format pipeline:

```
Ralphy chatbot session
  -> Ralphy creates issues: `bd create` per task (CLI)
  -> bd stores internally
  -> Ralph Loop: `bd ready --json --limit 1` (JSON)
  -> Issue.parse(json_dict) (Python dataclass)
  -> Issue.as_xml() (XML string)
  -> `opencode run <XML> --model <M> --agent ralph`
  -> OpenCode loads PROMPT.xml as system prompt (XML)
```

- JSON = bd CLI output format, consumed by Ralph Loop
- XML = agent input format (Issue.as_xml()) + system prompt (PROMPT.xml)
- No other document format exists in the pipeline

## A3. Dependency Chain

**Decision:** `bd create --deps` must be populated by Ralphy for sequential tasks.

- Format: `--deps "type:id"` (e.g., `blocks:bd-15`, `discovered-from:bd-20`)
- Ralphy encodes task order as explicit deps so `bd ready` respects sequencing
- This ensures Ralph Loop processes tasks in the correct order
- The agent itself can also create deps at runtime (PROMPT.xml Step 2)

## A4. Mid-Loop Issue Updates

**Decision:** Issues can be created, modified, and deleted directly via `bd` CLI. Full CRUD.

### Supported operations

| Action | How |
|--------|-----|
| Add new task | `bd create "New task" --deps "<dep-id>"` -- loop picks it up via `bd ready` polling |
| Cancel/skip a task | `bd close <id>` or `bd update <id> --status blocked` -- direct, no workaround needed |
| Modify a task | `bd update <id> --description "..." --acceptance "..."` -- update fields directly |
| Re-prioritize | `bd update <id> --priority <0-4>` |
| Append context | `bd update <id> --append-notes "new context"` |

### Why this works

- Loop calls `bd ready` each iteration -- sees current state of all issues, including modifications
- The agent reads the issue once at the start of its run (via `Issue.as_xml()`) -- modifications to not-yet-picked-up issues are always reflected
- `bd` handles its own state consistency
- Direct CRUD is simpler than creating blocking meta-issues for every change

### Gaps requiring fixes (extended bd wrapper)

- `update_issue()` in `pkgs/bd/main.py` only supports status/assignee -- extend to expose priority, labels, description, acceptance, append-notes
- This extension benefits both the UI team (for human-driven updates) and Ralphy (for issue refinements)

### Bugs fixed (2026-03-20)

1. **Match statement bug** in loop.py:249 -- `AgentStatus.HELP` matched before `BLOCKED | HELP`, making BLOCKED a dead branch. Fixed: separated into distinct HELP and BLOCKED arms.
2. **HELP status silent** -- logged warning but left issue IN_PROGRESS assigned to ralph. Fixed: now calls `cleanup_failed_iteration(status=BLOCKED)` so the issue becomes visible and the loop moves on.
