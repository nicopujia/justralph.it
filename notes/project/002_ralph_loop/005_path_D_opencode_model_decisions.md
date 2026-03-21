# Path D: OpenCode & Model Strategy Decisions

Date: 2026-03-21

## D13. Model Strategy

**Decision:** Sonnet 4.6 for the demo. Kimi K2.5 (or equivalent cheap Chinese model) for production.

- Model is configurable via `--model` flag on `ralph loop` (already implemented)
- Demo: `ralph loop --model openrouter/anthropic/claude-sonnet-4.6` (exact string TBD per OpenRouter naming)
- Production: `ralph loop --model opencode/kimi-k2.5` or similar
- No code change needed -- backend passes the right model string per environment

## D14. OpenCode is a Hard Dependency

**Decision:** OpenCode is the runtime. Everything in Ralph Loop executes via OpenCode.

- No abstraction layer needed
- The `Agent` class in `core/agent.py` shells out to `opencode run` directly
- All agent behavior is controlled by `opencode.jsonc` (config) and `PROMPT.xml` (system prompt)
- Both files are symlinked into the project root by `ralph init`

## D15. OpenCode Config File Discovery

**Decision:** `Agent.run()` subprocess must run with `cwd=base_dir` so OpenCode finds its config.

### Gap found

`Agent.run()` passes `**self._kwargs` to `subprocess.Popen` but no `cwd` was ever set -- not in the loop, not in the agent, not in the default hooks. OpenCode would fail to find `opencode.jsonc` and `PROMPT.xml` if the loop was started from a different directory.

### Fix applied (2026-03-21)

In `_create_agent()` (loop.py), added:
```python
extra_kwargs.setdefault("cwd", str(self.cfg.base_dir))
```

- Uses `setdefault` so hooks can override if needed
- Default is always `base_dir` (where `ralph init` symlinks the config files)
- OpenCode's `--agent ralph` flag loads the agent config from `opencode.jsonc` in cwd

### Config file chain

```
base_dir/
  opencode.jsonc -> /path/to/ralph/opencode.jsonc  (symlink)
  PROMPT.xml     -> /path/to/ralph/PROMPT.xml       (symlink)
  prod/          (worktree, where code lives)
  dev/           (worktree)
```

OpenCode runs in `base_dir`, finds `opencode.jsonc`, loads agent "ralph" config, which references `{file:./PROMPT.xml}` relative to cwd.

## D16. Subagent Limits

**Decision:** "Use up to 1000 subagents" in PROMPT.xml is aspirational, not literal.

- Practical limits: VPS CPU/RAM/disk, API rate limits, OpenCode concurrency model
- `_check_resources()` in loop.py already monitors and stops if threshold exceeded (default 95%)
- No code change needed -- resource monitoring handles self-throttling
