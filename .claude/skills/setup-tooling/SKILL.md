---
name: setup-tooling
description: Configure linters and formatters for the project (ruff, mypy for Python; eslint, prettier for TypeScript). Use when user wants code quality tooling, mentions "linting", "formatting", "ruff", "mypy", "eslint", or "prettier".
---

# Setup Tooling

Configure code quality tools for both Python and TypeScript.

## When to Use

- Setting up a new project or repo
- User asks for linting, formatting, or type checking
- User mentions ruff, mypy, eslint, prettier, or "code quality tooling"
- After qa_reviewer flags missing tooling

## Workflow

### Step 1: Detect Existing Config

Check what's already configured:
```bash
# Python
grep -c "ruff" pyproject.toml 2>/dev/null || echo "ruff: not configured"
grep -c "mypy" pyproject.toml 2>/dev/null || echo "mypy: not configured"

# TypeScript
ls client/.eslintrc* client/eslint.config.* 2>/dev/null || echo "eslint: not configured"
ls client/.prettierrc* client/prettier.config.* 2>/dev/null || echo "prettier: not configured"
```

### Step 2: Python Setup (ruff + mypy)

**Add to `pyproject.toml`**:
```toml
[tool.ruff]
target-version = "py313"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM", "TCH"]
ignore = ["E501"]  # line length handled by formatter

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.13"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false  # start permissive, tighten later
check_untyped_defs = true
```

**Install**:
```bash
uv add --dev ruff mypy
```

**Verify**:
```bash
uv run ruff check pkgs/ server/
uv run ruff format --check pkgs/ server/
uv run mypy pkgs/ server/ --ignore-missing-imports
```

### Step 3: TypeScript Setup (eslint + prettier)

**Install**:
```bash
cd client && bun add -d eslint @eslint/js typescript-eslint prettier eslint-config-prettier
```

**Create `client/eslint.config.js`**:
```javascript
import eslint from "@eslint/js";
import tseslint from "typescript-eslint";
import prettierConfig from "eslint-config-prettier";

export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  prettierConfig,
  {
    rules: {
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "@typescript-eslint/no-explicit-any": "warn",
    },
  }
);
```

**Create `client/.prettierrc`**:
```json
{
  "semi": true,
  "singleQuote": false,
  "tabWidth": 2,
  "trailingComma": "es5",
  "printWidth": 100
}
```

**Verify**:
```bash
cd client && bunx eslint src/
cd client && bunx prettier --check src/
```

### Step 4: Add Scripts

**Add to `pyproject.toml`**:
```toml
[project.scripts]
lint = "ruff check pkgs/ server/"
format = "ruff format pkgs/ server/"
typecheck = "mypy pkgs/ server/ --ignore-missing-imports"
```

**Add to `client/package.json` scripts**:
```json
{
  "lint": "eslint src/",
  "format": "prettier --write src/",
  "format:check": "prettier --check src/"
}
```

### Step 5: Fix Initial Violations

- Run `uv run ruff check --fix` to auto-fix Python issues
- Run `uv run ruff format` to format Python
- Run `cd client && bunx prettier --write src/` to format TypeScript
- Review remaining eslint warnings and fix manually

## Notes

- Start with permissive configs and tighten over time
- ruff replaces flake8, isort, and pyupgrade -- don't install those separately
- mypy `disallow_untyped_defs = false` initially to avoid blocking; python_improver can tighten
- Use `# noqa` and `// eslint-disable-next-line` sparingly and with justification
