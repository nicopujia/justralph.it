# --- BEGIN SECURITY CHECKS ---
# Prevent committing .env files and files containing secret patterns.
# This script is designed to be sourced from .git/hooks/pre-commit.

# 1. Check for .env files in staged changes
_sec_env_files=$(git diff --cached --name-only --diff-filter=ACR | grep -E '(^|/)\.env($|\.)' || true)
if [ -n "$_sec_env_files" ]; then
  echo >&2 "ERROR: Commit rejected — .env file(s) detected in staged changes:"
  echo >&2 "$_sec_env_files"
  echo >&2 ""
  echo >&2 "Remove them with: git reset HEAD <file>"
  echo >&2 "To bypass this check (not recommended): git commit --no-verify"
  exit 1
fi

# 2. Check staged diff content for secret-like patterns with actual values
# Matches added lines (+) containing KEY=value where value is non-empty
# and not just empty quotes. Skips comments and auto-generated beads files.
# The pattern requires the secret keyword to appear as a standalone assignment
# (not embedded in JSON or prose), preceded by start-of-line, whitespace, or "export".
_sec_files=$(git diff --cached --name-only --diff-filter=ACM | grep -v '^\.beads/' || true)
_sec_diff=""
if [ -n "$_sec_files" ]; then
  _sec_diff=$(echo "$_sec_files" | xargs -I{} git diff --cached -U0 -- "{}" | \
    grep -E '^\+[^+]' | \
    grep -v '^\+\s*#' | \
    grep -E '^\+\s*(export\s+)?(API_KEY|SECRET|PASSWORD|PRIVATE_KEY)=' | \
    grep -vE '(API_KEY|SECRET|PASSWORD|PRIVATE_KEY)=\s*$' | \
    grep -vE '(API_KEY|SECRET|PASSWORD|PRIVATE_KEY)=\s*""?\s*$' | \
    grep -vE "(API_KEY|SECRET|PASSWORD|PRIVATE_KEY)=\\s*''?\\s*$" || true)
fi

if [ -n "$_sec_diff" ]; then
  echo >&2 "ERROR: Commit rejected — possible secret(s) detected in staged changes:"
  echo >&2 "$_sec_diff"
  echo >&2 ""
  echo >&2 "If these are not real secrets, use: git commit --no-verify"
  exit 1
fi
# --- END SECURITY CHECKS ---
