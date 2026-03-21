# Path F: Ralph Loop Internals Decisions

Date: 2026-03-21

## F21. Match Statement Bug

**Already fixed** in commit 0bda3c4 (Path A/D session). Separated HELP and BLOCKED into distinct match arms.

## F22. Crash Recovery Git cwd

**Decision:** All git utility functions now accept a `cwd` parameter targeting the prod worktree.

### Problem

`git reset --hard` and branch operations in state.py and git.py ran with no explicit cwd. In the bare repo + worktree layout, these commands must target the `prod` worktree where code changes happen -- not the bare repo root.

### Fix applied

- `utils/git.py`: refactored `cleanup_branch()`, `ensure_on_main()`, `reset_git_state()` to accept `cwd` and use the `_run()` helper consistently. Added `hard_reset(cwd)`.
- `core/state.py`: `State.__init__()` now accepts `prod_dir`. `check_crash_recovery()` and `cleanup_failed_iteration()` pass it to git functions.
- `cmds/loop.py`: constructs State with `prod_dir=cfg.base_dir / PROD_WORKTREE`. Passes same cwd to `reset_git_state()` in `_create_agent()`.

## F23. Subprocess Timeout

**Decision:** Keep default at 600s (10 minutes). Document recommendation but no code change.

- Already configurable via `--subprocess-timeout`
- Recommendation: for complex issues, increase to 1800s (30 min) via CLI flag
- Awaiting CEO confirmation before changing the default
- If an issue exceeds timeout, the safety net catches stuck processes

## F24. Polling vs Event-Driven

**Decision:** Keep polling for the hackathon. 30s poll_interval is sufficient.

- Already configurable via `--poll-interval`
- Single VPS, one loop instance -- no efficiency concern
- Post-hackathon optimization: backend could write `restart.ralph` after issue creation to force immediate re-evaluation
