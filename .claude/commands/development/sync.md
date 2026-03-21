Safe-sync the local repo with the remote GitHub repository (https://github.com/nicopujia/justralph.it).
This command preserves ALL local work (untracked files, uncommitted changes) while pulling remote updates.

## Steps

### 1. AUDIT — Show full state before touching anything
Run these commands and present a summary table to the user:
- `git fetch origin` — get latest remote state
- `git status --short` — show all local changes (staged, unstaged, untracked)
- `git log --oneline HEAD..origin/main` — list remote commits we don't have
- `git log --oneline origin/main..HEAD` — list local commits not on remote
- `git diff --stat HEAD` — show tracked file modifications

Categorize local changes into:
- **Tracked modifications** (staged or unstaged edits/deletions to files git knows about) — THESE NEED STASHING
- **Untracked files** (new local files) — SAFE, git pull never touches these
- **Local-only commits** (not pushed) — could cause merge conflicts

If there are NO remote commits to pull, report "Already up to date" and stop.

### 2. STASH — Protect tracked modifications
If there are any staged or unstaged changes to tracked files:
- Run `git stash push -m "safe-sync-$(date +%Y%m%d-%H%M%S)"` to save them
- Confirm the stash was created with `git stash list`

If working tree is clean (no tracked modifications), skip this step.

### 3. PULL — Fast-forward only
- Run `git pull --ff-only origin main`
- If fast-forward fails (diverged history), STOP and tell the user. Do NOT rebase or merge without explicit instruction.

### 4. UNSTASH — Restore local modifications
If a stash was created in step 2:
- Run `git stash pop`
- If pop conflicts, report the conflicts and let the user decide how to resolve

### 5. GHOST FILE DETECTION — Find stale untracked files in restructured directories
After pulling, check if any remote commits renamed/moved/deleted files in directories that also have untracked local files. This catches "ghost files" — old files that linger locally after a remote restructure.

Run `git diff --name-status <old-HEAD>..<new-HEAD>` and identify directories where files were Deleted (D) or Renamed (R). Then cross-reference with `git ls-files --others --exclude-standard` in those same directories.

If ghost files are found:
- Present a table showing: directory, number of ghost files, what the remote restructured
- Recommend `git clean -fd <directory>` for each affected directory
- **ASK the user before running git clean** — never auto-delete
- If user approves, run `git clean -fd` scoped to only the affected directories

If no ghost files are found, skip this step silently.

### 6. REPORT — Concise summary
Show:
- Previous HEAD → New HEAD (commit hashes + messages)
- Number of new commits pulled
- Files changed by the pull (brief `--stat` summary)
- Whether stash was used and if it restored cleanly
- Ghost files cleaned (if any), or "none detected"
- Remaining untracked files count (just count, no full list)

## Rules
- Do NOT commit anything
- Do NOT push anything
- Do NOT delete untracked files without explicit user approval (ghost cleanup requires confirmation)
- Do NOT rebase without explicit user instruction
- ALWAYS stash before pulling if there are tracked modifications
- ALWAYS report state before and after
- ALWAYS ask before running git clean, even for ghost files
