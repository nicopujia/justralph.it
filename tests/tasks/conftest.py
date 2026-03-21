from pathlib import Path

import pytest


@pytest.fixture
def tasks_dir(tmp_path: Path) -> Path:
    """Empty dir for tasks.yaml to live in."""
    return tmp_path
