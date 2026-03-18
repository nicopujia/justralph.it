# Ralph

Autonomous agent that processes Beads issues using OpenCode.

Ralph claims ready issues from a Beads tracker, delegates work to [OpenCode](https://opencode.ai), handles completion or failure, and repeats until stopped. Includes crash recovery, resource monitoring, signal file controls, and customizable lifecycle hooks.

## Install

```sh
uv tool install ralph
```

## Run

```sh
cd your-project/
ralph --help
ralph
```

On first run, creates a `.ralph/` dir with default hooks and a `.gitignore` for runtime artifacts. 

## How it works

Each iteration:

1. Check for stop/restart signal files
2. Check disk, RAM, and CPU usage against threshold
3. Poll for the next ready issue (`bd ready`)
4. Claim issue: set status to `in_progress`, assignee to `ralph`
5. Reset git state: checkout main, delete previous `ralph/[issue-id]` branch
6. Run OpenCode subprocess with `--agent ralph` and stream output
7. Parse final status from last XML tag: `DONE`, `HELP`, `BLOCKED`
8. Handle completion or failure, run lifecycle hooks

On failure: exponential backoff (capped at 5 min). After `--max-retries` consecutive failures, writes stop file and exits.

## Signal files

Create these in `.ralph/` to control the loop:

- **`stop.ralph`** -- Graceful stop. Content logged as reason.
- **`restart.ralph`** -- Stop, call `post_loop` hook, restart from `pre_loop`.

Checked both during iterations and while polling for issues, so Ralph responds even when idle.

## Crash recovery

State written to `.ralph/state.json` before each iteration, cleared after success. On restart after a crash:

1. Run `git reset --hard` to discard partial changes
2. Set interrupted issue back to `open`, clear assignee
3. Restore iteration counter to resume from crash point
4. Clean up state file

## Logging

Format: `[YYYY-MM-DD HH:MM:SS] [LEVEL] [module] message`

- `.ralph/logs/main.log` -- All iterations, persistent
- `.ralph/logs/iteration_N.log` -- Per-iteration logs

Both streams also output to stdout.

## Hooks

Customize Ralph's lifecycle by editing `.ralph/hooks.py`:

```python
from ralph.hooks import Hooks

class CustomHooks(Hooks):
    def pre_loop(self, cfg):
        """Run once before the main loop starts."""
        pass

    def pre_iter(self, cfg, issue, iteration):
        """Run before each iteration."""
        pass

    def post_iter(self, cfg, issue, iteration, status, error):
        """Run after each iteration (status = Agent.Status, error = Exception | None)."""
        pass

    def post_loop(self, cfg, iterations_completed):
        """Run once after the main loop finishes."""
        pass

    def extra_args_kwargs(self, cfg, issue):
        """Return (args, kwargs) to pass to Agent constructor."""
        return (), {}
```

All methods are abstract. The scaffolded template provides no-op implementations.

## Agent behavior

Ralph runs OpenCode with `--agent ralph`, which uses the included `PROMPT.xml` as instructions. The prompt defines Ralph's workflow:

1. **Planning** - Understand project vision and scope
2. **Analysis** - Research codebase, check blockers, file issues if needed
3. **Design** - Identify solutions, list test scenarios (TDD)
4. **Development** - Outside-in TDD (integration + unit tests)
5. **Deployment** - Run full test suite, merge to main, deploy if applicable
6. **Maintenance** - Update docs, commit with `Closes: [issue-id]`
7. **Finish** - Output final status

Ralph outputs one of three status values:
- `<Status>COMPLETED ASSIGNED ISSUE</Status>` - Issue solved successfully
- `<Status>HUMAN HELP ABSOLUTELY NEEDED</Status>` - Blocked by credential/access issue
- `<Status>FOUND NEW BLOCKER ISSUE</Status>` - Discovered blocking dependency

The status is parsed from the last non-empty line of OpenCode's output.
