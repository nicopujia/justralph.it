# Path E: Beads (bd) Architecture Decisions

Date: 2026-03-21

## E17. bd is a Standalone Binary

**Decision:** bd is a standalone Go CLI binary, pre-installed on the VPS.

- Stores state locally in the project directory (scoped per base_dir)
- Installed alongside OpenCode and Ralph as a tool dependency (like git)
- No vendoring/embedding needed

## E18. Keep CLI Wrapper, Extend It

**Decision:** Keep the thin CLI wrapper in pkgs/bd/main.py. No direct storage access.

### Current wrapper surface

- `get_next_ready_issue()` -- bd ready --json --limit 1
- `update_issue(id, status, assignee)` -- bd update
- `close_issue(id)` -- bd close
- `Issue.parse(dict)` / `Issue.as_xml()` -- data conversion

### Expansion needed for our work

| Function | bd CLI command | Purpose |
|----------|---------------|---------|
| `update_issue()` extended | `bd update --priority --labels --description --acceptance --design --append-notes` | Full CRUD per A4 decision |
| `list_issues()` | `bd list --json` | UI issues panel (B6) |
| `get_issue(id)` | `bd show <id> --json` | Issue detail view for UI |
| `create_issue()` | `bd create` with all flags | Programmatic issue creation (for Ralphy integration and agent runtime) |

Priority: `update_issue()` extension and `list_issues()` are needed first.

## E19. Concurrent Access

**Decision:** Low risk for hackathon. One loop, one VPS, sequential issue processing.

- Only concurrent scenario: loop reads via `bd ready` while UI/Ralphy writes via `bd create`/`bd update`
- bd CLI likely uses atomic file operations
- Not a concern for demo scope

## E20. update_issue() Falsy Check Bug

**Decision:** Fixed. Changed `if status:` / `if assignee:` to `if status is not None:` / `if assignee is not None:`.

The bug: `assignee=""` (empty string) is falsy in Python, so `bd.update_issue(id, assignee="")` never sent `--assignee ""` to the CLI. The assignee was never actually cleared during cleanup.

Fix applied in pkgs/bd/main.py.
