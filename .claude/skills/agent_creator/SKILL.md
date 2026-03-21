---
name: agent_creator
description: This skill should be used when creating a new .claude/agents/*.md file for the justralph.it project. Provides the workflow, template guidance, and validation checklist for producing project-compliant agent files. Invoke alongside the agent_creator agent.
---

# Agent Creator Skill

Produce a complete, valid `.claude/agents/*.md` file that routes correctly, operates autonomously, and passes the `agent_updater` quality checklist.

## When to Use

- User wants to create a new agent for a specific role in the project
- An existing agent's scope is insufficient and a distinct new agent is warranted
- You need to verify whether a new agent is needed or if extending an existing one is better

## Workflow

### Step 1: Load References
Read both reference files before starting:
- `references/agent_template_guide.md` -- section-by-section instructions for filling the template
- `references/existing_agents_index.md` -- current agent scopes (overlap check)

### Step 2: Confirm Requirements
Before writing, confirm these five things are defined:
1. **Trigger**: What user phrase or task type invokes this agent?
2. **Output**: What exactly does it produce? (specific files, reports, decisions)
3. **Reads**: Which existing project files does it need? (must all exist in `pkgs/`, `server/`, `client/`)
4. **Writes**: Which files may it create or modify?
5. **Pipeline position**: Does it hand off to or receive from another agent?

If any are undefined, ask. Start with trigger + output -- those determine everything else.

### Step 3: Overlap Check
Scan `references/existing_agents_index.md`. If a current agent already covers this domain:
- Propose extending the existing agent's scope (add a responsibility) instead of creating a new one.
- Only proceed with a new file if the role is genuinely distinct.

### Step 4: Fill the Template
Follow `references/agent_template_guide.md`. Work section by section:

| Section | Priority | Notes |
|---------|----------|-------|
| `description` | Critical | Written first. Determines routing. Must start "Use this agent when..." |
| `model` | High | haiku=mechanical, sonnet=structured workflow, opus=deep reasoning |
| `Reads First` | High | Only list paths that exist in `pkgs/`, `server/`, `client/` -- verify with Read/Glob |
| Output Contract | High | Real file paths only. Vague descriptions fail the quality checklist. |
| Core Responsibilities | Medium | 2-5 sections. Action verbs. Domain-specific. |
| Operating Protocol | Medium | Discovery -> Execution -> Validation. Explicit steps. |
| Anti-Patterns | Optional | Include only if this agent enforces standards or reviews code. |

### Step 5: Write and Register
1. Write to `.claude/agents/{snake_case_name}.md`
2. Confirm all placeholder values are replaced
3. Confirm line count is 100-170
4. Update `references/existing_agents_index.md` with: `{name}: {one-line scope}`

### Step 6: Validate
Run the quality checklist before declaring done:

- [ ] All file paths in "Reads First" exist in the project (`pkgs/`, `server/`, `client/`)
- [ ] Instructions align with `CLAUDE.md` rules (uv tooling, conventional commits, concise docs, no em-dashes)
- [ ] No references to MT4, EA, MQL4, trading, or non-existent patterns
- [ ] Output Contract is complete with real paths
- [ ] Done-when criteria are measurable ("Done when X" not "when it looks good")
- [ ] `description` field: starts "Use this agent when...", max 2 sentences
- [ ] Line count: 100-170 lines
