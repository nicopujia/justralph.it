# Agent Template Guide

Explains each section of a justralph.it agent file -- what it is, how to fill it, and what makes it good vs. bad.

---

## Frontmatter

### `name`
The snake_case identifier. Used in logs and cross-agent references.
- Good: `loop_orchestrator`, `task_store`, `state_recovery`
- Bad: `LoopOrchestrator`, `loop-orchestrator`, `my agent`

### `description`
**The most important field.** Claude uses this for routing -- if it's wrong, the agent never gets invoked or gets invoked at the wrong time.
- Must start with "Use this agent when..."
- 1-2 sentences max
- Describe the trigger condition, not what the agent does
- Good: `"Use this agent when modifying or debugging the Ralph Loop orchestration logic in pkgs/ralph/cmds/loop.py."`
- Bad: `"This agent helps with loop development and has expertise in Python."` (describes capabilities, not trigger)

### `model`
| Model | Use when |
|-------|----------|
| `haiku` | Mechanical, deterministic tasks: file generation, format validation, simple transformations |
| `sonnet` | Most agents: structured workflows, analysis, code review, scaffolding, documentation |
| `opus` | Deep creative/reasoning: issue decomposition, prompt engineering, complex architecture decisions |

### `color`
Semantic, not arbitrary:
| Color | Domain |
|-------|--------|
| `purple` | Core logic, orchestration, deep reasoning |
| `blue` | Creation, scaffolding, building new things |
| `green` | Execution, testing, running processes |
| `orange` | Maintenance, auditing, updates |
| `red` | Risk gates, safety checks |
| `gray` | Standards enforcement, pattern checking |
| `teal` | Documentation, knowledge management |

---

## Opening Line
One declarative sentence after the frontmatter. Not a paragraph -- one sentence.
- Good: `You are the **Loop Orchestrator** -- a specialist in the Ralph agent loop lifecycle.`
- Bad: `You are a helpful AI assistant specializing in Python development.`

---

## Core Identity
2-4 sentences. Personality + approach + the quality the agent embodies.
- Good: Mentions the domain (Ralph loop, tasks, git worktrees), a concrete work style (systematic, conservative), and one thing the agent cares about above all else.
- Bad: Generic statements like "You are detail-oriented and strive for excellence."

---

## Mission
1-2 sentences. What you deliver. Not personality.
- Good: `Maintain crash recovery and state persistence to ensure the Ralph Loop can survive unexpected termination and resume cleanly.`
- Bad: `Help developers manage state better.`

---

## Critical Constraints
Optional. Only include hard limits that override user instructions.
- Good for: agents that must never touch certain files, read-only agents, safety gates
- Omit if there are no genuine non-negotiables

---

## Reads First
Mandatory. Every path must exist. Verify with Read/Glob before including.
**Always include as first item**: `CLAUDE.md -- project rules`
Domain-specific files come after. Common ones for this project:
- `pkgs/ralph/config.py` -- configuration dataclass
- `pkgs/ralph/core/agent.py` -- Agent class and AgentStatus enum
- `pkgs/ralph/core/events.py` -- EventBus and EventType
- `pkgs/ralph/core/state.py` -- State persistence
- `pkgs/ralph/core/hooks.py` -- Hooks lifecycle interface
- `pkgs/ralph/cmds/loop.py` -- main loop orchestration
- `pkgs/ralph/utils/git.py` -- git operations
- `pkgs/tasks/main.py` -- Task dataclass and task store

---

## Allowed to Edit
Mandatory. Be explicit. Anything not listed is off-limits.
- List directories with trailing `/` when the agent creates files within them
- List specific files when the agent modifies them
- Good: `pkgs/ralph/core/state.py` -- state persistence logic
- Bad: `Any relevant files` (too vague)

---

## Core Responsibilities
2-5 numbered sections. Each is a distinct duty.
- Start each section name with an action noun: "Review", "Generate", "Validate", "Analyze"
- 2-4 bullets per section, concrete actions
- Avoid restating the mission -- these are the HOW, not the WHY

---

## Agent Coordination (Optional)
Only include for agents in a multi-step pipeline.
If the agent works standalone (user calls it directly, no chain), omit this section.

---

## Operating Protocol
Three phases -- always:
**Phase 1: Discovery** -- What to read, gather, confirm before starting. List actual files.
**Phase 2: Execution** -- Step-by-step main work. Ordered list. Concrete enough that another agent could follow it.
**Phase 3: Validation** -- Quality checks before declaring done. Each check should be binary (pass/fail).

---

## Anti-Patterns (Optional)
Include only if this agent enforces standards or reviews work.
Format: `Do not X -- do Y instead`
Keep it to 3-6 items.

---

## Output Contract
Mandatory. The structured promise of what this agent delivers.

| Field | Content |
|-------|---------|
| **Action taken** | Describe what was done (past tense) |
| **Output location** | Real file path or directory |
| **Verification** | How to confirm it worked |

**Done when**: Single, measurable criterion. "When X exists and Y is verified."

---

## Interaction Style
3-5 bullets. Match the agent's domain.
- A loop agent is precise and references specific state transitions
- A docs agent is structured and references exact section names
- A git agent references branch names and tag conventions

---

## Closing Line
One memorable sentence. The agent's philosophy or commitment.

---

## Line Count Target
- Minimum: ~100 lines (too short = incomplete)
- Maximum: ~170 lines (too long = agent tries to do too much)
- If you exceed 170 lines: compress "Core Responsibilities" prose
