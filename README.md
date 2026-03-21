# justralph.it

## Setup

### 1. Clone

Ralph uses worktrees on a bare repo structure. You should do the same.

```sh
git clone --bare https://github.com/nicopujia/just-ralph-it.git justralph.it/.git
cd justralph.it
git worktree add main
git worktree add dev
```

You may want to add the following `AGENTS.md` file to the project root.

```md
You are working in a bare repo structure:

- `prod/`: main branch worktree
- `dev/`: dev branch worktree
- `.git/`

When making changes, you should work as follows:

1. Ensure main and dev are at sync between each other and with remote
2. Create a branch from dev
3. Make changes while committing frequently
4. Stop and ask whether to continue or not unless instructed not to
5. Rebase to dev
6. Rebase to main
7. Delete the branch you created
8. Push

<CommitMessages>
    Use conventional commits.
    Mostly lowercase.
    Abbreviate when obvious (e.g. `deps`, `cfg`, `init`, `impl`, `refactor`, `rm`, `mv`, etc.).
    Keep subjects short.
    If you include a body, keep it concise.
    <Examples>
        <Example>
            feat: impl username/password auth

            Closes: ex-001
        </Example>
        <Example>
            docs: update setup instructions in README

            Replace pip with uv.
        </Example>
    </Examples>
</CommitMessages>
```

### 2. Install dependencies

Then, inside each worktree, run:

```sh
uv sync
uv pip install -e pkgs/bd -e pkgs/ralph
```

### 3. Run the services

Server:

```bash
cd ./server
fastapi dev ./server/main.py
```

Client:

```bash
cd ./client
bun dev
```

## Test

```sh
uv run pytest
```
