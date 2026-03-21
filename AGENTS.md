Be extremely concise. Sacrifice grammar for the sake of concision.

## Architecture

justralph.it is a web platform: users describe a project idea via chatbot (Ralphy), which extracts requirements and generates tasks. An autonomous AI loop (Ralph) then executes those tasks.

- Backend: Python 3.13+, FastAPI, SQLite (db at `/tmp/ralph-sessions/ralph.db`)
- Frontend: React 19, Vite, Bun, Radix UI, Tailwind
- AI runtime: OpenCode (`opencode run` subprocess) -- no beads/bd CLI
- Task store: YAML-backed, local (`pkgs/tasks/main.py`)
- Session isolation: each user session gets its own `/tmp/ralph-sessions/{id}/` with a git repo + ralph scaffolding

## Architecture Decisions

- OpenCode (`opencode run`) as AI runtime -- not beads/bd CLI
- YAML task store over external DB (simplicity, git-friendly)
- Session isolation via temp dirs with per-session git repos
- No git worktrees -- each session gets a fresh `git init`
- In-memory session store (demo scope, no distributed state)

## Project Structure

```
pkgs/ralph/    # Ralph Loop: config, runner, agent subprocess, events, hooks, git utils
pkgs/tasks/    # YAML-backed task store (Task dataclass, CRUD, parallel groups)
server/        # FastAPI: sessions, chatbot, auth (GitHub OAuth), SQLite db
client/        # React 19 frontend: Vite + Bun + Radix UI + Tailwind
tests/         # pytest tests
.ralphy/       # Ralphy config (project-specific hooks, rules, logs)
PROMPT.xml     # system prompt for Ralph agents (symlinked into sessions)
```

## Session Model

Each session = isolated dir at `/tmp/ralph-sessions/{id}/`.
Contains: git repo, tasks.yaml, .ralphy/, PROMPT.xml symlink, opencode.jsonc symlink.
In-memory `_sessions` dict + SQLite for persistence across restarts.
Running sessions have a daemon thread with RalphyRunner.

## Tooling

- Python: `uv run <cmd>`, `uv add <pkg>`
- Frontend: `bun dev`, `bun build` (inside `client/`)
- Tests: `uv run pytest`
- Lint: `uv run ruff check .`
- Server: `fastapi dev ./server/main.py`
- Client: `cd client && bun dev`

## Environment Variables

- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` -- GitHub OAuth app credentials
- `ANTHROPIC_API_KEY` or `OPENCODE_API_KEY` -- AI runtime key

## Documentation

- Update existing docs whenever code changes.
- Document the non-obvious concisely.
- Do not use em-dashes.

## Commit Messages

Use conventional commits.
Mostly lowercase.
Abbreviate when obvious (e.g. `deps`, `cfg`, `init`, `impl`, `refactor`, `rm`, `mv`, etc.).
Keep subjects short.
If you include a body, keep it concise.

```
<Examples>
  <Example>
    feat: impl username/password auth

    Closes: ex-001
  </Example>
  <Example>
    docs: update setup instructions in README

    Replace pip with uv.
  </Example>
</Examples>
```
