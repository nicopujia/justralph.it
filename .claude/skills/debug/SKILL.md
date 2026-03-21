---
name: debug
description: Systematic debugging workflow for reproducing, isolating, and fixing bugs. Use when encountering errors, unexpected behavior, test failures, or when the user says "debug", "trace", "root cause", or "why is this broken".
---

# Debug

Systematic debugging workflow: reproduce, isolate, trace, fix, verify.

## When to Use

- User encounters an error or unexpected behavior
- Tests fail for unclear reasons
- User says "debug", "trace", "root cause", "why is this broken"
- A feature works in one context but fails in another

## Workflow

### Step 1: Reproduce
Confirm the error is reproducible.
- Run the failing command or trigger the failing behavior
- Capture the exact error output (traceback, status code, console error)
- Note the environment: which session, which task, which module
- If not reproducible, gather more context before proceeding

### Step 2: Isolate
Narrow down to the specific file and function.
- Use Grep to search for error messages, exception types, or failing function names
- Read the stack trace bottom-up -- the root cause is usually at the bottom
- For Python: check `pkgs/ralph/core/`, `server/`, `pkgs/tasks/` in that order
- For TypeScript: check `client/src/hooks/`, `client/src/components/` in that order
- Identify the FIRST incorrect behavior, not the last symptom

### Step 3: Trace
Follow the call chain from error to root cause.
- Read the function where the error occurs
- Trace inputs: where do the arguments come from?
- Check state: is there shared mutable state (EventBus, sessions dict, task store)?
- For async issues: check thread safety, race conditions, missing awaits
- For import errors: check circular imports, missing __init__.py exports

### Step 4: Fix
Implement the minimal change that resolves the root cause.
- Fix the root cause, not the symptom
- Prefer the smallest change that solves the problem
- If the fix requires changes across multiple files, note the scope
- Follow error_handler patterns for new exception handling
- Do not introduce new dependencies unless absolutely necessary

### Step 5: Verify
Confirm the fix works and doesn't break anything else.
- Re-run the originally failing command/test
- Run related tests: `uv run pytest tests/` (Python) or `bun test` (TypeScript)
- Check for regressions in adjacent functionality
- If the bug had no test, write one to prevent regression

## Key Files by Error Domain

| Domain | Key Files |
|--------|-----------|
| Loop crashes | `pkgs/ralph/core/ralphy_runner.py`, `pkgs/ralph/core/agent.py` |
| Task errors | `pkgs/tasks/main.py` |
| API errors | `server/main.py`, `server/sessions.py` |
| Chatbot errors | `server/chatbot.py` |
| WebSocket issues | `server/main.py` (WS endpoints), `client/src/hooks/useWebSocket.ts` |
| State/recovery | `pkgs/ralph/core/state.py`, `pkgs/ralph/utils/backup.py` |
| Git operations | `pkgs/ralph/utils/git.py` |
| Frontend rendering | `client/src/components/`, `client/src/hooks/` |

## Tips

- Always read the full traceback before guessing
- Check git blame if the bug is in recently changed code
- For intermittent failures: look for race conditions, timing issues, or shared state
- Use `uv run python -c "..."` for quick Python debugging
- The fix should be obvious once you understand the root cause -- if it's not, you haven't found the root cause yet
