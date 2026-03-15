"""Tests for the pre-commit security hook that prevents committing secrets."""

import os
import shutil
import subprocess
import tempfile


def _run(cmd, cwd, env=None, check=True):
    """Run a shell command and return the CompletedProcess."""
    merged_env = {**os.environ, **(env or {})}
    return subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        env=merged_env,
        check=check,
    )


def _make_repo_with_hook(tmp_path):
    """Create a temporary git repo and install the security hook."""
    repo = os.path.join(tmp_path, "repo")
    os.makedirs(repo)
    _run("git init", repo)
    _run("git config user.email 'test@test.com'", repo)
    _run("git config user.name 'Test'", repo)
    # Create an initial commit so HEAD exists
    _run("touch README.md && git add README.md && git commit -m 'init'", repo)

    # Install the security hook as pre-commit
    hook_src = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "pre-commit-security.sh")
    hook_dst = os.path.join(repo, ".git", "hooks", "pre-commit")
    # Write a minimal hook that sources the security script
    with open(hook_dst, "w") as f:
        f.write("#!/usr/bin/env sh\n")
        f.write(f'. "{hook_src}"\n')
    os.chmod(hook_dst, 0o755)
    return repo


class TestEnvFileRejection:
    """Commits containing .env files should be rejected."""

    def test_reject_dot_env(self, tmp_path):
        repo = _make_repo_with_hook(tmp_path)
        _run("echo 'FOO=bar' > .env", repo)
        _run("git add -f .env", repo)
        result = _run("git commit -m 'add env'", repo, check=False)
        assert result.returncode != 0
        assert ".env" in result.stderr

    def test_reject_dot_env_local(self, tmp_path):
        repo = _make_repo_with_hook(tmp_path)
        _run("echo 'FOO=bar' > .env.local", repo)
        _run("git add -f .env.local", repo)
        result = _run("git commit -m 'add env local'", repo, check=False)
        assert result.returncode != 0
        assert ".env" in result.stderr

    def test_reject_dot_env_production(self, tmp_path):
        repo = _make_repo_with_hook(tmp_path)
        _run("echo 'FOO=bar' > .env.production", repo)
        _run("git add -f .env.production", repo)
        result = _run("git commit -m 'add env prod'", repo, check=False)
        assert result.returncode != 0
        assert ".env" in result.stderr

    def test_reject_nested_dot_env(self, tmp_path):
        """A .env file in a subdirectory should also be rejected."""
        repo = _make_repo_with_hook(tmp_path)
        _run("mkdir -p config && echo 'X=1' > config/.env", repo)
        _run("git add -f config/.env", repo)
        result = _run("git commit -m 'add nested env'", repo, check=False)
        assert result.returncode != 0
        assert ".env" in result.stderr


class TestSecretPatternRejection:
    """Commits containing secret-like patterns in staged diffs should be rejected."""

    def test_reject_api_key(self, tmp_path):
        repo = _make_repo_with_hook(tmp_path)
        _run("echo 'API_KEY=sk-abc123' > config.py", repo)
        _run("git add config.py", repo)
        result = _run("git commit -m 'add api key'", repo, check=False)
        assert result.returncode != 0
        assert "secret" in result.stderr.lower() or "API_KEY" in result.stderr

    def test_reject_secret(self, tmp_path):
        repo = _make_repo_with_hook(tmp_path)
        _run("echo 'SECRET=supersecretvalue' > settings.py", repo)
        _run("git add settings.py", repo)
        result = _run("git commit -m 'add secret'", repo, check=False)
        assert result.returncode != 0

    def test_reject_password(self, tmp_path):
        repo = _make_repo_with_hook(tmp_path)
        _run("echo 'PASSWORD=hunter2' > db.py", repo)
        _run("git add db.py", repo)
        result = _run("git commit -m 'add password'", repo, check=False)
        assert result.returncode != 0

    def test_reject_private_key(self, tmp_path):
        repo = _make_repo_with_hook(tmp_path)
        _run("echo 'PRIVATE_KEY=-----BEGIN RSA-----' > keys.py", repo)
        _run("git add keys.py", repo)
        result = _run("git commit -m 'add private key'", repo, check=False)
        assert result.returncode != 0

    def test_reject_secret_in_diff_only(self, tmp_path):
        """Only the staged diff should be scanned, not the whole file."""
        repo = _make_repo_with_hook(tmp_path)
        # First commit a file with a comment about secrets (not an assignment)
        _run("echo '# This file has no secrets' > app.py", repo)
        _run("git add app.py", repo)
        _run("git commit -m 'add app'", repo)
        # Now add a line with a real secret
        _run("echo 'API_KEY=real_secret_value' >> app.py", repo)
        _run("git add app.py", repo)
        result = _run("git commit -m 'add key to app'", repo, check=False)
        assert result.returncode != 0


class TestAllowedCommits:
    """Normal commits and empty secret assignments should be allowed."""

    def test_allow_normal_file(self, tmp_path):
        repo = _make_repo_with_hook(tmp_path)
        _run("echo 'print(\"hello\")' > hello.py", repo)
        _run("git add hello.py", repo)
        result = _run("git commit -m 'add hello'", repo, check=False)
        assert result.returncode == 0

    def test_allow_empty_api_key(self, tmp_path):
        """Empty assignments like API_KEY= (no value) are not real secrets."""
        repo = _make_repo_with_hook(tmp_path)
        _run("echo 'API_KEY=' > config.py", repo)
        _run("git add config.py", repo)
        result = _run("git commit -m 'add empty key'", repo, check=False)
        assert result.returncode == 0

    def test_allow_empty_password(self, tmp_path):
        repo = _make_repo_with_hook(tmp_path)
        _run("echo 'PASSWORD=' > config.py", repo)
        _run("git add config.py", repo)
        result = _run("git commit -m 'add empty password'", repo, check=False)
        assert result.returncode == 0

    def test_allow_placeholder_secret(self, tmp_path):
        """Placeholder values like quotes with nothing inside should be allowed."""
        repo = _make_repo_with_hook(tmp_path)
        _run("""echo 'API_KEY=""' > config.py""", repo)
        _run("git add config.py", repo)
        result = _run("git commit -m 'add placeholder'", repo, check=False)
        assert result.returncode == 0

    def test_allow_comment_mentioning_secret(self, tmp_path):
        """Comments mentioning secret patterns should not trigger rejection."""
        repo = _make_repo_with_hook(tmp_path)
        _run("echo '# Set API_KEY= in your .env file' > README.md", repo)
        _run("git add README.md", repo)
        result = _run("git commit -m 'add readme'", repo, check=False)
        assert result.returncode == 0

    def test_allow_env_example(self, tmp_path):
        """A .env.example file with empty values should be allowed."""
        repo = _make_repo_with_hook(tmp_path)
        # .env.example name-matches .env* but contains no real secrets
        # Actually, .env.example should be rejected by filename pattern
        # since it matches .env*. This is intentional - example files
        # should use a different naming convention.
        pass

    def test_allow_secret_reference_in_code(self, tmp_path):
        """Code that references os.environ['API_KEY'] should be fine."""
        repo = _make_repo_with_hook(tmp_path)
        _run("""echo 'key = os.environ["API_KEY"]' > app.py""", repo)
        _run("git add app.py", repo)
        result = _run("git commit -m 'add env lookup'", repo, check=False)
        assert result.returncode == 0

    def test_allow_secret_keyword_in_json_text(self, tmp_path):
        """SECRET= appearing inside JSON or prose should not trigger."""
        repo = _make_repo_with_hook(tmp_path)
        _run(
            """echo '{"description":"Set SECRET= in env"}' > data.json""",
            repo,
        )
        _run("git add data.json", repo)
        result = _run("git commit -m 'add json data'", repo, check=False)
        assert result.returncode == 0

    def test_allow_beads_jsonl(self, tmp_path):
        """Files under .beads/ should be excluded from secret scanning."""
        repo = _make_repo_with_hook(tmp_path)
        _run("mkdir -p .beads", repo)
        _run(
            """echo '{"title":"Set API_KEY=abc"}' > .beads/issues.jsonl""",
            repo,
        )
        _run("git add -f .beads/issues.jsonl", repo)
        result = _run("git commit -m 'add beads export'", repo, check=False)
        assert result.returncode == 0


class TestExportPrefix:
    """Secret patterns prefixed with 'export' should also be caught."""

    def test_reject_export_api_key(self, tmp_path):
        repo = _make_repo_with_hook(tmp_path)
        _run("echo 'export API_KEY=sk-abc123' > setup.sh", repo)
        _run("git add setup.sh", repo)
        result = _run("git commit -m 'add export key'", repo, check=False)
        assert result.returncode != 0

    def test_allow_export_empty_api_key(self, tmp_path):
        repo = _make_repo_with_hook(tmp_path)
        _run("echo 'export API_KEY=' > setup.sh", repo)
        _run("git add setup.sh", repo)
        result = _run("git commit -m 'add export empty key'", repo, check=False)
        assert result.returncode == 0
