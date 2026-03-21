# justralph.it

A web platform where you describe your project idea to an AI chatbot (Ralphy), which extracts requirements and generates tasks, then an autonomous AI coding agent (Ralph) builds your project.

## How It Works

1. **Chat with Ralphy** -- describe your idea, answer questions about requirements
2. **Review generated tasks** -- Ralphy extracts structured tasks with dependencies
3. **Just Ralph It** -- Ralph (autonomous AI loop) executes tasks, creates code, pushes to GitHub

## Architecture

- **Backend**: FastAPI (Python 3.13+) with SQLite persistence (`/tmp/ralph-sessions/ralph.db`)
- **Frontend**: React 19 + Vite + Bun + Radix UI + Tailwind CSS
- **AI Runtime**: OpenCode (opencode.ai) running `opencode-go/kimi-k2.5` model
- **Task Store**: YAML-backed, no external CLI needed
- **Session isolation**: each session gets `/tmp/ralph-sessions/{id}/` with its own git repo

## Setup

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- [Bun](https://bun.sh/) (for frontend)
- [OpenCode](https://opencode.ai/) (AI runtime)

### Install

```sh
git clone https://github.com/nicopujia/justralph.it
cd justralph.it
uv sync
```

### Environment Variables

```sh
# GitHub OAuth (optional, for repo creation)
export GITHUB_CLIENT_ID="..."
export GITHUB_CLIENT_SECRET="..."
```

### Run

```sh
# Server
fastapi dev ./server/main.py

# Client (separate terminal)
cd client && bun install && bun dev
```

### Test

```sh
uv run pytest
```

### Lint

```sh
uv run ruff check .
```

## Project Structure

```
pkgs/ralph/     # Ralph Loop engine (config, runner, agent, events, hooks)
pkgs/tasks/     # YAML task store (CRUD, parallel groups, reconciliation)
server/         # FastAPI: sessions, chatbot, GitHub OAuth, SQLite
client/         # React 19 frontend
tests/          # pytest tests
PROMPT.xml      # Agent system prompt
```
