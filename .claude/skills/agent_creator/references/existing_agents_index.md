# Existing Agents Index

Quick scope reference for overlap checking. Update this file after every new agent is created.

**Format**: `name | model | color | scope (one line)`

---

## Current Agents

### Meta/Tooling Agents

| Name | Model | Color | Scope |
|------|-------|-------|-------|
| `agent_creator` | sonnet | blue | Creating new `.claude/agents/*.md` files from the template. Checks overlap, fills template, registers in index. |
| `agent_updater` | sonnet | orange | Auditing all `.claude/agents/*.md` files for drift from project standards. Patches outdated paths, deprecated patterns, alignment issues. Does NOT create new agents. |
| `docs_maintainer` | sonnet | teal | Keeping README.md, CLAUDE.md, and module docstrings in sync with source code. Read-only on source files. |
| `task_architect` | opus | purple | Translating feature ideas into structured task trees with dependencies and acceptance criteria. Creates tasks via YAML task store only. |

### Loop Core Agents

| Name | Model | Color | Scope |
|------|-------|-------|-------|
| `loop_orchestrator` | sonnet | purple | Main loop logic: `_iterate`, `_handle_status`, signal/resource checks, hooks lifecycle. Owns `cmds/loop.py`, `core/hooks.py`, `templates/hooks.py`. |
| `agent_subprocess` | sonnet | green | Agent subprocess wrapper and event bus. Owns `core/agent.py`, `core/events.py`, `core/exceptions.py`. |
| `state_recovery` | sonnet | orange | Crash recovery and issue backup/restore. Owns `core/state.py`, `utils/backup.py`. |

### Git/Infrastructure Agents

| Name | Model | Color | Scope |
|------|-------|-------|-------|
| `git_operations` | sonnet | gray | All git operations: branches, tags, merges, rollbacks. Legacy bare repo/worktree functions kept for backwards compat. Owns `utils/git.py`. |
| `config_init` | sonnet | blue | Configuration system and project scaffolding. Owns `config.py`, `cmds/init.py`, `cmds/__init__.py`, `main.py`. |

### Task Store Agents

| Name | Model | Color | Scope |
|------|-------|-------|-------|
| `task_store` | sonnet | blue | Python task store: Task dataclass, CRUD functions, YAML file ops. Owns `pkgs/tasks/main.py`. |

### Server/Client Agents

| Name | Model | Color | Scope |
|------|-------|-------|-------|
| `server_websocket` | sonnet | green | FastAPI server: WebSocket endpoint, REST API, EventBus consumption. Owns `server/main.py`. |
| `client_developer` | sonnet | blue | React 19 frontend: Bun runtime, Radix UI, Tailwind, WebSocket client. Owns `client/src/**`. |

### Prompt/Testing Agents

| Name | Model | Color | Scope |
|------|-------|-------|-------|
| `prompt_engineer` | opus | purple | Ralph's system prompt and OpenCode config. Owns `PROMPT.xml`, `opencode.jsonc`. |
| `integration_tester` | sonnet | green | Cross-subsystem tests: loop lifecycle, crash recovery, git ops, event bus. Owns `tests/**`. |

---

## Scope Boundary Notes

- `loop_orchestrator` vs `agent_subprocess`: loop_orchestrator orchestrates iterations, agent_subprocess manages the OpenCode subprocess. Loop calls Agent, not the reverse.
- `state_recovery` vs `loop_orchestrator`: state_recovery handles persistence/recovery mechanics, loop_orchestrator calls it at the right lifecycle points.
- `git_operations` vs `loop_orchestrator`: git_operations owns all git functions, loop_orchestrator calls them during status handling.
- `task_store` vs `task_architect`: task_store maintains the Python task store code, task_architect uses it to create tasks.
- `agent_subprocess` vs `prompt_engineer`: agent_subprocess manages the process, prompt_engineer manages what the process receives as instructions.
- `docs_maintainer` vs `agent_updater`: docs_maintainer handles project docs (README, docstrings), agent_updater handles agent files only.
- `server_websocket` vs `client_developer`: server provides the API, client consumes it. API contract is shared boundary.

---

## Full Workflow Pipeline

```
IDEA -> task_architect -> (creates tasks)
     -> ralph loop picks up tasks -> loop_orchestrator
     -> agent_subprocess (runs OpenCode) -> prompt_engineer (PROMPT.xml)
     -> state_recovery (crash safety) + git_operations (merge/tag)
     -> server_websocket (events to UI) -> client_developer (displays)

Maintenance:
  agent_updater -> (patches agent files)
  agent_creator -> (creates new agent files)
  docs_maintainer -> (keeps docs in sync)
  integration_tester -> (validates cross-subsystem behavior)
```
