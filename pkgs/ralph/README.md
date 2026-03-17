# Ralph

Autonomous coding agent loop. Picks up issues, delegates work to [OpenCode](https://opencode.ai), and repeats until told to stop.

## Install

```sh
uv tool install ralph
```

## Run

```sh
cd your-project/
ralph
```

On first run, creates a `.ralph/` dir with default hooks and a `.gitignore` for runtime artifacts.

## CLI flags

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
| `--stop-file` | `.ralph/stop.ralph` | Stop signal file |
| `--restart-file` | `.ralph/restart.ralph` | Restart signal file |
| `--state-file` | `.ralph/state.json` | Crash-recovery state file |
| `--log-file` | `.ralph/logs/main.log` | Main log file |
| `--logs-dir` | `.ralph/logs/` | Per-iteration log directory |
| `--base-dir` | `.ralph/` | Base directory for all runtime files |

## How it works

Each iteration:

1. Check for stop/restart signal files
2. Check disk, RAM, and CPU usage against threshold
3. Fetch the next ready issue (`bd ready`)
4. Set issue to `in_progress`, assignee to `ralph`
5. Spawn OpenCode with the prompt and stream output
6. Parse the final `<Status>` XML tag for the outcome
7. Run lifecycle hooks

On failure, retries with exponential backoff (capped at 5 min). After `--max-retries` consecutive failures, writes a stop file.

## Signal files

Create in `.ralph/` to control the loop:

- **`stop.ralph`** -- graceful stop. Content is logged as the reason.
- **`restart.ralph`** -- stop, call `post_loop`, restart from `pre_loop`.

Also checked while polling, so Ralph responds even when idle.

## Crash recovery

State is written to `.ralph/state.json` before each iteration and cleared after. On restart after a crash:

1. `git reset --hard`
2. Issue set back to `open`
3. Iteration counter restored
4. State file cleaned up

## Logging

Format: `[timestamp] [LEVEL] [module] message`

- `.ralph/logs/main.log` -- all iterations
- `.ralph/logs/iteration_N.log` -- per iteration

Both also print to stdout.

## Hooks

Edit `.ralph/hooks.py`:

```python
from ralph.hooks import Hooks

class CustomHooks(Hooks):
    def pre_loop(self, cfg): ...
    def pre_iter(self, cfg, issue, iteration): ...
    def post_iter(self, cfg, issue, iteration, status, error): ...
    def post_loop(self, cfg, iterations_completed): ...
    def extra_args_kwargs(self, cfg, issue): return (), {}
```

All methods are abstract. The default scaffold provides no-op implementations.

## Prompt template

`PROMPT.xml` is shipped with the package and is **immutable**. It's a Python format string receiving the `Agent` instance as `{self}`.

Template variables: `{self.issue.id}`, `{self.issue.title}`, `{self.DONE}`, `{self.HELP}`, `{self.BLOCKED}`.

`__getattr__` resolves any `Status` enum name into an instruction string for the `<Status>` XML tag.

Inter-iteration notes are handled by `AGENTS.md` (injected by OpenCode).
