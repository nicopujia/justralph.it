"""Scaffold a Ralph project directory."""

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import ralph as ralph_module

from ..config import (
    HOOKS_FILENAME,
    RALPHY_DIR_NAME,
    Config,
)
from ..utils.git import is_repo
from . import Command

logger = logging.getLogger(__name__)

# Resolve paths relative to Ralph's installed package root
PACKAGE_ROOT = Path(ralph_module.__file__).parent
TEMPLATES = PACKAGE_ROOT / "templates"

RALPHY_GITIGNORE_CONTENT = "logs/\nstate.json\n*.ralph\nbackups/\n"

DEFAULT_CONFIG_YAML = """\
project:
  name: ""
  language: ""
  framework: ""
  description: ""

commands:
  test: ""
  lint: ""

boundaries:
  never_touch:
    - .ralphy/
"""

EMPTY_TASKS_YAML = "tasks: []\n"


@dataclass
class InitConfig(Config):
    """Configuration for the init command."""

    force: bool = field(
        default=False,
        metadata={"help": "Delete and re-create the project directory"},
    )
    remote: str = field(
        default="",
        metadata={"help": "GitHub repo URL to add as origin remote"},
    )


class Init(Command):
    help = "Scaffold a Ralph project"
    config = InitConfig
    cfg: InitConfig

    def run(self) -> None:
        """Scaffold a project for use with Ralph + ralphy.

        Target structure::

            base_dir/
                .git/              # standard git repo
                .ralphy/           # ralphy config directory
                |-- config.yaml    # project config
                |-- rules.txt      # coding rules for AI
                |-- hooks.py       # lifecycle hooks
                |-- .gitignore
                |-- logs/
                tasks.yaml         # task store
                PROMPT.xml -> ...  # symlink to ralph package
        """
        root = self.cfg.base_dir

        if self.cfg.force and root.exists():
            shutil.rmtree(root)
            logger.info("Removed %s", root)

        root.mkdir(parents=True, exist_ok=True)

        # Initialize git repo if needed (standard, not bare)
        if not is_repo(root):
            subprocess.run(
                ["git", "init"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            logger.info("Initialized git repo at %s", root)

        # Run ralphy --init if ralphy is available (creates .ralphy/ scaffold)
        if shutil.which("ralphy"):
            result = subprocess.run(
                ["ralphy", "--init"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                logger.info("Ran ralphy --init")
            else:
                logger.warning("ralphy --init failed: %s", result.stderr.strip())

        # Scaffold .ralphy/ (fill in anything ralphy --init may have missed)
        self._scaffold_ralphy_dir(root)

        # Create tasks.yaml if missing
        tasks_file = root / "tasks.yaml"
        if not tasks_file.exists():
            tasks_file.write_text(EMPTY_TASKS_YAML)
            logger.info("Created %s", tasks_file)

        # Symlink PROMPT.xml
        self._symlink_config(root, "PROMPT.xml")

        if self.cfg.remote:
            subprocess.run(
                ["git", "remote", "add", "origin", self.cfg.remote],
                cwd=root, capture_output=True,
            )

        logger.info("Initialized %s", root)

    def _scaffold_ralphy_dir(self, root: Path) -> None:
        """Create .ralphy/ with config, hooks, rules, .gitignore, logs dir."""
        ralphy_dir = root / RALPHY_DIR_NAME
        ralphy_dir.mkdir(parents=True, exist_ok=True)
        (ralphy_dir / "logs").mkdir(parents=True, exist_ok=True)

        # config.yaml
        config_path = ralphy_dir / "config.yaml"
        if not config_path.exists():
            config_path.write_text(DEFAULT_CONFIG_YAML)
            logger.info("Created %s", config_path)

        # rules.txt
        rules_path = ralphy_dir / "rules.txt"
        if not rules_path.exists():
            rules_path.write_text("")
            logger.info("Created %s", rules_path)

        # hooks.py
        hooks_path = ralphy_dir / HOOKS_FILENAME
        if not hooks_path.exists():
            hooks_path.write_text(self._read_template(HOOKS_FILENAME))
            logger.info("Created %s", hooks_path)

        # .gitignore
        gitignore_path = ralphy_dir / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text(RALPHY_GITIGNORE_CONTENT)
            logger.info("Created %s", gitignore_path)

    @staticmethod
    def _read_template(name: str) -> str:
        """Read a built-in template file by name."""
        return (TEMPLATES / name).read_text()

    @staticmethod
    def _symlink_config(root: Path, filename: str) -> None:
        """Create symlink from project root to Ralph's installed config file."""
        symlink_path = root / filename
        config_path = PACKAGE_ROOT / filename

        if symlink_path.exists() or symlink_path.is_symlink():
            symlink_path.unlink()
        symlink_path.symlink_to(config_path)
        logger.info("Created symlink %s -> %s", symlink_path, config_path)
