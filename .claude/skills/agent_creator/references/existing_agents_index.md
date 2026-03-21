# Existing Agents Index

Quick scope reference for overlap checking. Update this file after every new agent is created.

**Format**: `name | model | color | scope (one line)`

**Pipeline**: Plan -> Code -> Test -> QA -> Docs (formal handoff chain)

---

## Current Agents

### Meta/Tooling

| Name | Model | Color | Scope |
|------|-------|-------|-------|
| `agent_creator` | sonnet | blue | Creating new `.claude/agents/*.md` files from the template. Checks overlap, fills template, registers in index. |
| `agent_updater` | sonnet | orange | Auditing all `.claude/agents/*.md` files for drift from project standards. Patches outdated paths, deprecated patterns, alignment issues. Does NOT create new agents. |

### Plan Stage

| Name | Model | Color | Scope |
|------|-------|-------|-------|
| `prd_writer` | opus | purple | Translating feature ideas into structured PRDs with phases, acceptance criteria, and agent assignments. Creates files in `docs/prds/`. |
| `task_architect` | opus | purple | Translating feature ideas/PRDs into structured task trees with dependencies and acceptance criteria. Creates tasks via YAML task store only. |

### Code Stage -- Loop Core

| Name | Model | Color | Scope |
|------|-------|-------|-------|
| `loop_orchestrator` | sonnet | purple | Main loop logic: `_iterate`, `_handle_status`, signal/resource checks, hooks lifecycle. Owns `cmds/loop.py`, `core/hooks.py`, `templates/hooks.py`. |
| `agent_subprocess` | sonnet | green | Agent subprocess wrapper and event bus. Owns `core/agent.py`, `core/events.py`. Raises exceptions defined by error_handler. |
| `state_recovery` | sonnet | orange | Crash recovery and issue backup/restore. Owns `core/state.py`, `utils/backup.py`. |

### Code Stage -- Infrastructure

| Name | Model | Color | Scope |
|------|-------|-------|-------|
| `git_operations` | sonnet | gray | All git operations: branches, tags, merges, rollbacks. Owns `utils/git.py`. |
| `config_init` | sonnet | blue | Configuration system and project scaffolding. Owns `config.py`, `cmds/init.py`, `cmds/__init__.py`, `main.py`. |
| `task_store` | sonnet | blue | Python task store: Task dataclass, CRUD functions, YAML file ops. Owns `pkgs/tasks/main.py`. |
| `error_handler` | sonnet | red | Exception hierarchy, retry/resilience patterns, graceful degradation. Owns `core/exceptions.py`. |

### Code Stage -- Server

| Name | Model | Color | Scope |
|------|-------|-------|-------|
| `server_websocket` | sonnet | green | FastAPI server: WebSocket endpoint, REST API routes, EventBus consumption. Owns `server/main.py`. Calls chatbot_engine and session_manager functions. |
| `chatbot_engine` | sonnet | purple | Ralphy chatbot: confidence scoring, EMA smoothing, readiness calculation, phase caps. Owns `server/chatbot.py`. |
| `session_manager` | sonnet | blue | Session lifecycle: CRUD, directory isolation, git init, runner bridging. Owns `server/sessions.py`. |

### Code Stage -- Client

| Name | Model | Color | Scope |
|------|-------|-------|-------|
| `client_developer` | sonnet | blue | React 19 frontend: Bun runtime, Radix UI, Tailwind, WebSocket client. Owns `client/src/**`. Builds new features. |

### Code Stage -- Quality

| Name | Model | Color | Scope |
|------|-------|-------|-------|
| `python_improver` | opus | orange | Python backend code quality: refactoring, type safety, error patterns, performance. Operates across `pkgs/**`, `server/**`. |
| `typescript_improver` | sonnet | orange | React/TypeScript code quality: component architecture, state management, accessibility, React 19 patterns. Operates across `client/src/**`. |
| `prompt_engineer` | opus | purple | Ralph's system prompt and OpenCode config. Owns `PROMPT.xml`, `opencode.jsonc`. |

### Test Stage

| Name | Model | Color | Scope |
|------|-------|-------|-------|
| `unit_tester` | sonnet | green | Unit tests: pytest (Python), bun test (TS). Coverage tracking, test maintenance. Owns `tests/**` for unit tests. |
| `integration_tester` | sonnet | green | Cross-subsystem tests: loop lifecycle, crash recovery, git ops, event bus. Owns `tests/**` for integration tests. |

### QA Stage

| Name | Model | Color | Scope |
|------|-------|-------|-------|
| `qa_reviewer` | opus | red | Full pipeline audit: code review, protocol compliance, test coverage, issue filing, auto-fix. THE gate before docs. |
| `security_auditor` | opus | red | Security audits: dependency CVEs, input validation, OWASP, auth patterns, subprocess safety. Invoked by qa_reviewer. |

### Observability

| Name | Model | Color | Scope |
|------|-------|-------|-------|
| `observability_engineer` | sonnet | gray | Structured logging setup (structlog/loguru), log instrumentation, logging conventions. |

### Docs Stage

| Name | Model | Color | Scope |
|------|-------|-------|-------|
| `docs_maintainer` | sonnet | teal | Keeping README.md, CLAUDE.md, and module docstrings in sync with source code. Read-only on source files. |
| `dependency_manager` | sonnet | orange | Python deps (pyproject.toml, uv.lock), JS deps (package.json, bun.lockb). Updates, audits, compat checks. |

---

## Scope Boundary Notes

- `loop_orchestrator` vs `agent_subprocess`: loop_orchestrator orchestrates iterations, agent_subprocess manages the OpenCode subprocess. Loop calls Agent, not the reverse.
- `state_recovery` vs `loop_orchestrator`: state_recovery handles persistence/recovery mechanics, loop_orchestrator calls it at the right lifecycle points.
- `git_operations` vs `loop_orchestrator`: git_operations owns all git functions, loop_orchestrator calls them during status handling.
- `task_store` vs `task_architect`: task_store maintains the Python task store code, task_architect uses it to create tasks.
- `agent_subprocess` vs `prompt_engineer`: agent_subprocess manages the process, prompt_engineer manages what the process receives as instructions.
- `docs_maintainer` vs `agent_updater`: docs_maintainer handles project docs (README, docstrings), agent_updater handles agent files only.
- `server_websocket` vs `client_developer`: server provides the API, client consumes it. API contract is shared boundary.
- `chatbot_engine` vs `server_websocket`: chatbot_engine owns `chatbot.py` business logic; server_websocket owns API routes that call it.
- `session_manager` vs `server_websocket`: session_manager owns `sessions.py`; server_websocket owns routes that call it.
- `unit_tester` vs `integration_tester`: unit = isolated function tests; integration = cross-subsystem tests.
- `python_improver` vs domain agents: domain agents change behavior; python_improver changes code quality without changing behavior.
- `typescript_improver` vs `client_developer`: client_developer builds new features; typescript_improver improves existing code quality.
- `qa_reviewer` vs `agent_updater`: qa_reviewer audits code + protocol compliance; agent_updater audits agent .md files specifically.
- `error_handler` vs `agent_subprocess`: error_handler defines exception hierarchy in `exceptions.py`; agent_subprocess raises them from `agent.py`.

---

## Full Workflow Pipeline

```
IDEA -> prd_writer -> (creates PRD)
     -> task_architect -> (creates tasks from PRD)
     -> Ralph Loop picks up tasks -> loop_orchestrator
     -> agent_subprocess (runs OpenCode) -> prompt_engineer (PROMPT.xml)
     -> state_recovery (crash safety) + git_operations (merge/tag)
     -> server_websocket (events to UI) -> client_developer (displays)
     -> unit_tester (validates changes)
     -> qa_reviewer (full audit, can invoke security_auditor)
     -> docs_maintainer (updates docs)

Code Quality (invoked during Code stage):
  python_improver -> (backend refactoring)
  typescript_improver -> (frontend refactoring)
  error_handler -> (exception patterns)

Cross-cutting:
  security_auditor -> (invoked by qa_reviewer)
  observability_engineer -> (logging setup)
  dependency_manager -> (dep management)

Meta:
  agent_updater -> (patches agent files)
  agent_creator -> (creates new agent files)
```
