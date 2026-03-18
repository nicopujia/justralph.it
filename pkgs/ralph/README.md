# Ralph CLI

## Setup

```sh
uv tool install ralph
ralph --help
```

Customize Ralph's lifecycle by editing `.ralph/hooks.py`:

## Signal files

Create these in `.ralph/` to control the loop:

- `stop.ralph`: Graceful stop once the current iteration finishes. File content logged as reason.
- `restart.ralph`: Stop, call `post_loop` hook, restart from `pre_loop`.

Checked both during iterations and while polling for issues, so Ralph responds even when idle.
