# Path B: Ralph Loop -> UI Integration Decisions

Date: 2026-03-20

## B5. Real-Time Updates Transport

**Decision:** Use the existing hooks system as the event source. Hooks push structured events to a FastAPI SSE or WebSocket endpoint that the React frontend subscribes to.

Why hooks:
- Already called at every lifecycle point in loop.py (pre_loop, pre_iter, post_iter, post_loop)
- Receive typed data: Config, Issue, AgentStatus, iteration index
- CustomHooks in `.ralph/hooks.py` is the designated extension point
- No log parsing needed

Transport (hackathon scope):
- In-process queue or file-based events between Ralph Loop and FastAPI server
- FastAPI exposes WebSocket/SSE endpoint to React frontend

## B6. UI Data Requirements

**Decision:** Two data streams feeding two UI panels.

### Panel A: Chat real-time messages
- Ralphy chatbot conversation (questions/answers)
- This is Ralphy's domain -- Ralph Loop does not produce this

### Panel B: Split view with two sub-panels

**Sub-panel B1: bd issues assigned**
- List of all issues with current status (open, in_progress, blocked, done)
- Currently active issue highlighted
- Source: `bd list --json` or equivalent, refreshed via hook events

**Sub-panel B2: Terminal-like code execution view**
- Real-time agent stdout (what OpenCode is doing right now)
- Similar to watching Claude Code execute in a terminal
- Source: `Agent.run()` generator output, streamed line-by-line via WebSocket

### Data structure per event

Tier 1 (structured, via hooks):
- Loop state: started, waiting_for_issues, processing, stopped
- Current issue: id, title, status, priority
- Iteration index
- Agent status: IDLE, WORKING, DONE, HELP, BLOCKED
- Resource usage: CPU/RAM/disk %
- Errors (if any)

Tier 2 (raw stream):
- Agent stdout lines from `Agent.run()` generator
- Forwarded to WebSocket alongside hook events

## B7. HELP Response Flow

**Decision:** Leverage existing bd CRUD + signal files + uploads directory.

Flow:
1. Ralph reports HELP -> agent has filed a blocking issue assigned to "Human" (per PROMPT.xml Step 2)
2. `post_iter` hook fires with status=HELP -> WebSocket pushes notification to UI
3. UI shows the blocking issue details to the user
4. User provides what's needed (API keys, files, verification) through the UI
5. UI writes files to `uploads/` directory (already designated in PROMPT.xml ProjectStructure)
6. UI calls `bd close <blocking-issue-id>` (direct CRUD, per A4 decision)
7. UI writes `restart.ralph` signal file (or calls API that does)
8. Ralph Loop restarts, finds original issue unblocked, picks it up

## B8. Notification Target

**Decision:** WebSocket push to the browser. No email/SMS/webhook for hackathon scope.

- React frontend maintains persistent WebSocket connection
- All events (status changes, HELP requests, completions) arrive in real-time
- Single channel, end to end: hook -> transport -> WebSocket -> browser
