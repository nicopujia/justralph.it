# just-ralph-it

A web app that automates the Ralph Wiggum technique end-to-end. The user signs in with GitHub, creates a project, gets interviewed by Ralphy (an AI chatbot that extracts a complete spec), and then clicks "Just Ralph It" to kick off the Ralph loop on the same VPS — which runs headless opencode against the generated beads issues until the project is built.

## Who it's for

Technical hackers (starting with the author himself) who fully own their code and the machine it runs on, and want to stop doing the tedious setup required to apply the Ralph Wiggum technique effectively.

## Success

The app can build itself: a user (Nico, at a hackathon) opens justralph.it, signs in with GitHub, creates a new project, gets interviewed by Ralphy until the spec is complete, clicks "Just Ralph It," and watches Ralph autonomously build and push the project to a new GitHub repo — without any manual setup.

## Platform

Web app (runs on a single VPS that also executes Ralph loops).

## Constraints

- Coding agent: headless opencode (already installed at `~/.npm-global/bin/opencode`), using Kimi K2 via OpenCode Zen (`opencode/kimi-k2.5`) for both this project's ralph.py and ralph_template.py (for new user projects)
- Ralph loop: based on existing `ralph.py` in this repo
- Issue tracking: beads (`bd`) — already initialized
- Auth: GitHub OAuth (not GitHub App); scopes: repo (create + push), read:user
- Each project gets its own new GitHub repo, auto-created and named after the project
- Project files live at `~/projects/<project_name>/` on the VPS
- Ralphy's system prompt is this repo's OpenCode system prompt, adapted for the web context. It lives in the opencode config for this repo — not in AGENTS.md. See the issue for how to adapt it.
- UI is functional only — minimal CSS for layout (two-panel, tabs, terminal view), no polish or design work in v1
- Light and dark mode via CSS `prefers-color-scheme` (no toggle — follows system theme)
- Ralph always looks for secrets in `~/projects/<project_name>/.env`. If a required secret is missing, Ralph files a HUMAN_NEEDED issue specifying the exact env var name needed
- No per-project VPS provisioning in v1
- No legacy codebase input in v1
- No multi-user collaboration in v1
- Backend: Python
- Frontend: HTMX (server-rendered HTML, SSE/WebSocket for real-time)
- Database: SQLite

## Issue Tracking

This project uses **bd** (beads) for ALL issue tracking.

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work atomically
bd close <id>         # Complete work
bd dolt push          # Push beads data to remote
```

## Non-Interactive Shell Commands

Always use non-interactive flags: `cp -f`, `mv -f`, `rm -f`, `rm -rf`, `apt-get -y`.

## Landing the Plane

Work is NOT complete until `git push` succeeds:

```bash
git pull --rebase && bd dolt push && git push
```

<!-- BEGIN BEADS INTEGRATION -->
## Issue Tracking with bd (beads)

**IMPORTANT**: This project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs, task lists, or other tracking methods.

### Why bd?

- Dependency-aware: Track blockers and relationships between issues
- Git-friendly: Dolt-powered version control with native sync
- Agent-optimized: JSON output, ready work detection, discovered-from links
- Prevents duplicate tracking systems and confusion

### Quick Start

**Check for ready work:**

```bash
bd ready --json
```

**Create new issues:**

```bash
bd create "Issue title" --description="Detailed context" -t bug|feature|task -p 0-4 --json
bd create "Issue title" --description="What this issue is about" -p 1 --deps discovered-from:bd-123 --json
```

**Claim and update:**

```bash
bd update <id> --claim --json
bd update bd-42 --priority 1 --json
```

**Complete work:**

```bash
bd close bd-42 --reason "Completed" --json
```

### Issue Types

- `bug` - Something broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

### Priorities

- `0` - Critical (security, data loss, broken builds)
- `1` - High (major features, important bugs)
- `2` - Medium (default, nice-to-have)
- `3` - Low (polish, optimization)
- `4` - Backlog (future ideas)

### Workflow for AI Agents

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task atomically**: `bd update <id> --claim`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked issue:
   - `bd create "Found bug" --description="Details about what was found" -p 1 --deps discovered-from:<parent-id>`
5. **Complete**: `bd close <id> --reason "Done"`

### Auto-Sync

bd automatically syncs via Dolt:

- Each write auto-commits to Dolt history
- Use `bd dolt push`/`bd dolt pull` for remote sync
- No manual export/import needed!

### Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems

For more details, see README.md and docs/QUICKSTART.md.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

<!-- END BEADS INTEGRATION -->
