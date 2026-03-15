# scripts/ directory

## pre-commit-security.sh

Shell script sourced by `.git/hooks/pre-commit` to block secrets from being committed.

### How it works

1. **Filename check**: Rejects any staged file matching `.env` or `.env.*` (anywhere in the tree).
2. **Content check**: Scans staged diffs for lines matching `API_KEY=`, `SECRET=`, `PASSWORD=`, `PRIVATE_KEY=` with non-empty values. Excludes `.beads/` files (auto-generated JSONL exports). Only matches lines where the pattern appears as a standalone assignment (start of line, optionally prefixed with `export`).

### Key decisions

- The content check scans `git diff --cached` output (only staged changes), not full file content — avoids false positives from existing content.
- `.beads/issues.jsonl` is excluded because it contains issue descriptions that may reference secret patterns in text form.
- The pattern requires the keyword at the start of the line (after optional whitespace/export) to avoid matching occurrences inside JSON, prose, or code strings like `os.environ["API_KEY"]`.
- Empty assignments (`API_KEY=`, `API_KEY=""`, `API_KEY=''`) are allowed since they're not real secrets.

### Bypassing

`git commit --no-verify` skips all pre-commit hooks (standard git behavior).

### Auto-install

`setup.sh` appends the security section to `.git/hooks/pre-commit` if not already present. The section sources this script by path.
