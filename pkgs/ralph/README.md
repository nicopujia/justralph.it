# Ralph

Autonomous coding agent loop. Ralph picks up issues from [Beads](https://github.com/steveyegge/beads), delegates work to [OpenCode](https://opencode.ai), and repeats until told to stop.

## Prerequisites

- Python >= 3.13
- [uv](https://docs.astral.sh/uv/)
- [OpenCode](https://opencode.ai) CLI (`opencode`) on `PATH`
- [Beads](https://github.com/steveyegge/beads) CLI (`bd`) on `PATH`

## Install

```sh
uv tool install ralph
```

Or from this repo:

```sh
uv pip install -e pkgs/bd -e pkgs/ralph
```

## Run

```sh
cd your-project/
ralph
```

On first run, Ralph creates a `.ralph/` directory in the current working directory with default hooks. The `.ralph/` dir should be committed -- it contains project-specific config. Add the runtime artifacts to your `.gitignore`:

```gitignore
.ralph/logs/
.ralph/state.json
.ralph/*.ralph
```

All options have sensible defaults. Override with CLI flags:

| Flag | Default | Description |
|------|---------|-------------|
| `--model` | `opencode/kimi-k2.5` | Model passed to OpenCode |
| `--prompt-file` | (shipped w/ package) | Prompt template (immutable) |
| `--max-iters` | `-1` (infinite) | Max iterations before stopping |
| `--max-retries` | `-1` (infinite) | Max consecutive failures before stopping |
| `--poll-interval` | `30` | Seconds between polls for new issues |
| `--subprocess-timeout` | `600` | Seconds before killing an OpenCode run |
| `--bd-timeout` | `30` | Seconds before timing out a `bd` command |
| `--vm-res-threshold` | `95` | Stop if disk, RAM, or CPU usage exceeds this % |
| `--stop-file` | `.ralph/stop.ralph` | Path to the stop signal file |
| `--restart-file` | `.ralph/restart.ralph` | Path to the restart signal file |
| `--state-file` | `.ralph/state.json` | Path to crash-recovery state file |
| `--log-file` | `.ralph/logs/main.log` | Main log file |
| `--logs-dir` | `.ralph/logs/` | Directory for per-iteration logs |
| `--base-dir` | `.ralph/` | Base directory for all runtime files |

## How it works

Each iteration:

1. Check for stop/restart signal files
2. Check disk, RAM, and CPU usage against threshold
3. Fetch the next ready issue from Beads (`bd ready`)
4. Set issue status to `in_progress` and assignee to `ralph`
5. Spawn OpenCode with the prompt template and stream its output
6. Parse the final `<status>` XML tag to determine the outcome
7. Run lifecycle hooks

On failure, Ralph retries with exponential backoff (capped at 5 min). After exceeding `--max-retries` consecutive failures, it writes a stop file and halts on the next iteration.

## Signal files

Create these files in `.ralph/` to control the loop at the next iteration boundary:

- **`stop.ralph`** -- Stop the loop gracefully. Optional file content is logged as the reason.
- **`restart.ralph`** -- Stop the current loop, call `post_loop`, then start a fresh loop from `pre_loop`. Optional content is logged as the reason.

```sh
echo "deploying new config" > .ralph/restart.ralph
```

Both files are also checked while polling for new issues, so Ralph responds even when idle.

## Crash recovery

Before each iteration, Ralph writes `.ralph/state.json` with the current issue ID and iteration index. The file is removed after the iteration completes. If Ralph is killed mid-iteration (OOM, power loss, etc.), on the next startup it:

1. Runs `git reset --hard` to discard partial changes
2. Sets the interrupted issue back to `open` status
3. Restores the iteration counter from the saved value
4. Cleans up the state file

## Logging

All logs use the format `[timestamp] [LEVEL] [module] message`.

- **`.ralph/logs/main.log`** -- Append-only log across all iterations.
- **`.ralph/logs/iteration_N.log`** -- Dedicated log for iteration N, including the OpenCode output.

Both are also printed to stdout.

## Per-project directory

Ralph creates a `.ralph/` directory in whatever project you run it from:

```
your-project/
  .ralph/
    hooks.py       # CustomHooks subclass -- override methods here
    logs/          # Log files
    state.json     # Crash-recovery state
    stop.ralph     # Create to stop the loop
    restart.ralph  # Create to restart the loop
```

## Hooks

Lifecycle hooks let you run custom code at each stage of the loop. Edit `.ralph/hooks.py` and override methods on `CustomHooks`:

```python
from ralph.hooks import Hooks

class CustomHooks(Hooks):
    def pre_loop(self, cfg):
        print("starting up")

    def post_iter(self, cfg, issue, iteration, status, error):
        if error:
            notify_slack(f"iteration {iteration} failed: {error}")
```

All methods are abstract and must be implemented (the default scaffold provides pass-through no-ops for each).

| Method | Args | Called when |
|--------|------|------------|
| `pre_loop` | `cfg` | Once before the loop starts |
| `pre_iter` | `cfg, issue, iteration` | Before each iteration |
| `post_iter` | `cfg, issue, iteration, status, error` | After each iteration |
| `post_loop` | `cfg, iterations_completed` | Once after the loop ends |
| `extra_args_kwargs` | `cfg, issue` | Before creating the Agent; return `(args, kwargs)` forwarded to it |

## Prompt template

`PROMPT.md` is shipped with the package and is **immutable**. It receives the `Agent` instance as `{self}`.

Available template variables:

- `{self.issue.id}` -- current issue ID
- `{self.issue.title}` -- current issue title
- `{self.DONE}` -- instruction string for the DONE status
- `{self.HELP}` -- instruction string for the HELP status
- `{self.BLOCKED}` -- instruction string for the BLOCKED status

The Agent's `__getattr__` resolves any `Status` enum member name into an instruction string that tells OpenCode to output the corresponding `<status>` XML tag.

Notes between iterations are handled by `AGENTS.md` files, which OpenCode injects automatically.

## Package structure

```
pkgs/ralph/           # the ralph package
  PROMPT.md           # immutable prompt template
  opencode.jsonc      # opencode config
  config.py           # Config dataclass and CLI arg parsing
  agent.py            # Agent class: spawns OpenCode, streams output, parses status
  hooks.py            # Hooks ABC (abstract base class)
  init.py             # Scaffolds .ralph/ dir and dynamically loads hooks
  loop.py             # Main loop and entry point
  state.py            # State persistence for crash recovery
pkgs/bd/              # separate package wrapping the Beads CLI
```
