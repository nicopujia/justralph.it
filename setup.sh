# Enable shared Dolt DB server for beads
export BEADS_DOLT_SHARED_SERVER=1

# Use god mode config for opencode
export OPENCODE_CONFIG=./opengod.jsonc

# Install pre-commit security hook if not already present
_hook_file="$(git rev-parse --show-toplevel 2>/dev/null)/.git/hooks/pre-commit"
if [ -f "$_hook_file" ]; then
  if ! grep -q "BEGIN SECURITY CHECKS" "$_hook_file" 2>/dev/null; then
    cat >> "$_hook_file" << 'HOOK_EOF'

# --- BEGIN SECURITY CHECKS ---
# Prevent committing .env files and files containing secret patterns.
# Source the security check script from the repo's scripts directory.
_sec_script="$(git rev-parse --show-toplevel 2>/dev/null)/scripts/pre-commit-security.sh"
if [ -f "$_sec_script" ]; then
  . "$_sec_script"
fi
# --- END SECURITY CHECKS ---
HOOK_EOF
    echo "Installed pre-commit security hook."
  fi
else
  echo "Warning: No pre-commit hook found at $_hook_file — skipping security hook install."
fi
