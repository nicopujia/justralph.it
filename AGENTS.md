# just-ralph-it

A web app that automates the Ralph Wiggum technique end-to-end. The user signs in with GitHub, creates a project, gets interviewed by Ralphy (an AI chatbot that extracts a complete spec), and then clicks "Just Ralph It" to kick off the Ralph loop on the same VPS — which runs headless opencode against the generated beads issues until the project is built.

## Who it's for

Technical hackers (starting with the author himself) who fully own their code and the machine it runs on, and want to stop doing the tedious setup required to apply the Ralph Wiggum technique effectively.

## Success

The app can build itself: a user (Nico, at a hackathon) opens justralph.it, signs in with GitHub, creates a new project, gets interviewed by Ralphy until the spec is complete, clicks "Just Ralph It," and watches Ralph autonomously build and push the project to a new GitHub repo — without any manual setup.

## Platform

Web app (runs on a single VPS that also executes Ralph loops).

## Constraints

- Coding agent: headless opencode (already installed at `~/.npm-global/bin/opencode`)
- Ralph loop: based on existing `ralph.py` in this repo
- Issue tracking: beads (`bd`) — already initialized
- Auth: GitHub App (not OAuth); must have repo read/write permissions for creating repos and pushing code
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
