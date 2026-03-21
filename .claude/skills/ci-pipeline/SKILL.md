---
name: ci-pipeline
description: Generate GitHub Actions CI/CD configuration for automated testing, linting, and deployment. Use when user wants continuous integration, mentions "CI", "CD", "GitHub Actions", "pipeline", or "workflow".
---

# CI Pipeline

Generate GitHub Actions workflows for automated quality checks and deployment.

## When to Use

- Setting up CI for the first time
- Adding new test/lint steps to existing pipeline
- User mentions "CI", "CD", "GitHub Actions", "pipeline", "workflow"
- Before first production deployment

## Workflow

### Step 1: Analyze Project

Detect the project setup:
- **Python**: Check `pyproject.toml` for test framework, linting tools, Python version
- **TypeScript**: Check `client/package.json` for test/build scripts
- **Both**: Check for Docker files, deployment configs

### Step 2: Generate CI Workflow

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.13

      - name: Install dependencies
        run: uv sync

      - name: Lint
        run: uv run ruff check pkgs/ server/

      - name: Format check
        run: uv run ruff format --check pkgs/ server/

      - name: Type check
        run: uv run mypy pkgs/ server/ --ignore-missing-imports

      - name: Test
        run: uv run pytest tests/ -v --tb=short

  typescript:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Bun
        uses: oven-sh/setup-bun@v2

      - name: Install dependencies
        working-directory: client
        run: bun install --frozen-lockfile

      - name: Lint
        working-directory: client
        run: bunx eslint src/

      - name: Type check
        working-directory: client
        run: bunx tsc --noEmit

      - name: Build
        working-directory: client
        run: bun run build
```

### Step 3: Optional Additions

**Add caching** (faster CI runs):
```yaml
      - name: Cache uv
        uses: actions/cache@v4
        with:
          path: ~/.cache/uv
          key: uv-${{ hashFiles('uv.lock') }}
```

**Add deployment step** (after tests pass):
```yaml
  deploy:
    needs: [python, typescript]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      # Add deployment steps here (e.g., SSH deploy, Docker push)
```

**Add PR checks** (required status checks):
- Go to GitHub repo Settings > Branches > Branch protection rules
- Require status checks: `python`, `typescript`

### Step 4: Verify

```bash
# Validate workflow syntax
gh workflow view ci.yml 2>/dev/null || echo "Push to GitHub to validate"

# Run locally (if act is installed)
act push
```

## Notes

- Use `--frozen-lockfile` for bun to ensure reproducible installs
- uv is faster than pip for CI -- no need for pip caching
- Keep CI fast: aim for < 3 minutes total
- Add `concurrency` to cancel in-progress runs on new pushes:
  ```yaml
  concurrency:
    group: ${{ github.workflow }}-${{ github.ref }}
    cancel-in-progress: true
  ```
