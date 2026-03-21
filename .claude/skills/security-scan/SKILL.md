---
name: security-scan
description: Run security checks across the codebase including dependency audits, code pattern analysis, and input validation review. Use when user mentions "security", "vulnerability", "audit", "CVE", or before deploying to production.
---

# Security Scan

Comprehensive security check: dependencies, code patterns, input validation, secrets.

## When to Use

- Before deploying to production
- After adding new dependencies
- User mentions "security", "vulnerability", "audit", "CVE"
- After adding new API endpoints or user input handling
- Periodic security hygiene checks

## Workflow

### Step 1: Dependency Audit

**Python**:
```bash
# Check for known vulnerabilities
uv run pip-audit
# Or if pip-audit not installed:
uv add --dev pip-audit && uv run pip-audit
```

**JavaScript**:
```bash
cd client && bun pm ls  # Review dependency tree
```

- Flag any package with known CVEs
- Check for outdated packages with security patches available
- Review transitive dependencies

### Step 2: Code Pattern Scan

Search for dangerous patterns in the codebase:

**Command injection**:
- `subprocess.run(..., shell=True)` -- should be shell=False
- `os.system()` -- should use subprocess instead
- String formatting in subprocess args -- should use list args

**Path traversal**:
- `open(user_input)` without path validation
- `os.path.join(base, user_input)` without canonicalization
- Session directory creation with unsanitized names

**Eval/exec**:
- `eval()`, `exec()` with any external input
- `importlib` with user-controlled module names

**Information disclosure**:
- Full tracebacks returned in API responses
- Sensitive config values in logs
- Debug mode enabled in production

### Step 3: Input Validation

Review all FastAPI endpoints in `server/main.py`:
- Are path parameters validated (regex patterns, length limits)?
- Are request bodies validated via Pydantic models?
- Are file uploads restricted (size, type)?
- Is the `_require_session` helper used consistently?
- Are error responses generic enough to not leak internals?

### Step 4: Secrets Scan

Search for hardcoded credentials:
- API keys, tokens, passwords in source files
- `.env` files committed to git
- Credentials in configuration files
- Check `.gitignore` includes sensitive file patterns

### Step 5: Report

Produce a structured findings report:

```
## Security Scan Report

### CRITICAL
- [finding]: [file:line] - [description] - [remediation]

### HIGH
- ...

### MEDIUM
- ...

### LOW / INFO
- ...

### Summary
- Dependencies: X clean, Y vulnerable
- Code patterns: X issues found
- Input validation: X endpoints reviewed, Y need fixes
- Secrets: X issues found
```

## Key Files to Scan

| File | Risk Area |
|------|-----------|
| `server/main.py` | API input validation, CORS config |
| `server/sessions.py` | Directory creation, path handling |
| `server/chatbot.py` | OpenCode subprocess calls |
| `pkgs/ralph/core/agent.py` | Subprocess execution |
| `pkgs/ralph/utils/git.py` | Git subprocess calls |
| `pkgs/tasks/main.py` | YAML deserialization, file locking |

## Related Agents

- **security_auditor**: For deep security analysis and remediation
- **dependency_manager**: For dependency updates after finding CVEs
