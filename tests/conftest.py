import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def tmp_project_dir(tmp_path: Path) -> Path:
    """Temp dir mimicking a ralph project: .ralphy/, tasks.yaml, git init."""
    (tmp_path / ".ralphy").mkdir()
    (tmp_path / ".ralphy" / "logs").mkdir()
    (tmp_path / "tasks.yaml").write_text("tasks: []\n")
    subprocess.run(
        ["git", "init"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "initial"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    return tmp_path


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Minimal git repo with initial commit."""
    subprocess.run(
        ["git", "init"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "initial"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    return tmp_path
