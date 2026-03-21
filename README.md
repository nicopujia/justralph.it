# justralph.it

## Setup

### 1. Clone

Ralph uses worktrees on a bare repo structure. You should do the same.

```sh
git clone --bare https://github.com/nicopujia/just-ralph-it.git justralph.it/.git
cd justralph.it
git worktree add dev -b dev main
git worktree add prod main
```

### 2. Install dependencies

Then, inside each worktree, run:

```sh
uv sync
uv pip install -e pkgs/bd -e pkgs/ralph
```

## Test

```sh
uv run pytest
```
