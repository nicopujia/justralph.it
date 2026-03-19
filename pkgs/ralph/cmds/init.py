"""Scaffold a Ralph project directory."""

import logging
import shutil
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from ..config import Config
from ..utils.git import (
    add_worktree,
    convert_to_bare,
    has_worktree,
    init_bare,
    is_repo,
)
from . import Command

logger = logging.getLogger(__name__)

TEMPLATES = resources.files("ralph.templates")


@dataclass
class InitConfig(Config):
    """Configuration for the init command."""

    force: bool = field(
        default=False,
        metadata={"help": "Delete and re-create the project directory"},
    )
    agents_md: Path = field(
        default=Path(""),
        metadata={
            "help": "Path to AGENTS.md template (default: built-in empty template)",
        },
    )


class Init(Command):
    help = "Scaffold a Ralph project with worktrees"
    config = InitConfig
    cfg: InitConfig

    def run(self) -> None:
        """Scaffold or reorganize a project into the Ralph worktree layout.

        Target structure::

            base_dir/
                .git/            # bare repo
                .ralph/          # ralph config (hooks, logs, state)
                AGENTS.md        # project instructions for agents
                opencode.jsonc   # OpenCode configuration
                PROMPT.xml       # agent system prompt
                prod/            # worktree on main
                dev/             # worktree on dev

        If base_dir is already a git repo, it is converted to bare and
        worktrees are added. Otherwise a fresh bare repo is created.
        """
        root = self.cfg.base_dir

        if self.cfg.force and root.exists():
            shutil.rmtree(root)
            logger.info("Removed %s", root)

        root.mkdir(parents=True, exist_ok=True)

        if is_repo(root):
            self._init_existing(root)
        else:
            self._init_fresh(root)

        self._scaffold_ralph_dir(root)
        self._write_template(root / "AGENTS.md", self._agents_md_content())
        self._write_template(root / "opencode.jsonc", self._read_template("opencode.jsonc"))
        self._write_template(root / "PROMPT.xml", self._read_template("PROMPT.xml"))

        logger.info("Initialized %s", root)

    # -- repo setup --------------------------------------------------------

    def _init_fresh(self, root: Path) -> None:
        """Create a bare repo with prod and dev worktrees."""
        init_bare(root)
        add_worktree(root, "prod", branch="main")
        add_worktree(root, "dev", branch="dev", new_branch=True)

    def _init_existing(self, root: Path) -> None:
        """Convert an existing repo to bare and add missing worktrees."""
        convert_to_bare(root)
        if not has_worktree(root, "prod"):
            add_worktree(root, "prod", branch="main")
        if not has_worktree(root, "dev"):
            add_worktree(root, "dev", branch="dev", new_branch=True)

    # -- ralph config files ------------------------------------------------

    def _scaffold_ralph_dir(self, root: Path) -> None:
        """Create .ralph/ with hooks, logs, and .gitignore."""
        ralph_dir = root / ".ralph"
        ralph_dir.mkdir(parents=True, exist_ok=True)
        (ralph_dir / "logs").mkdir(parents=True, exist_ok=True)

        self._write_template(ralph_dir / "hooks.py", self._read_template("hooks.py"))
        self._write_template(ralph_dir / ".gitignore", "logs/\nstate.json\n*.ralph\n")

    # -- helpers -----------------------------------------------------------

    def _agents_md_content(self) -> str:
        """Return AGENTS.md content from user-supplied path or built-in template."""
        src = self.cfg.agents_md
        if src and src != Path(""):
            return src.read_text()
        return self._read_template("AGENTS.md")

    @staticmethod
    def _read_template(name: str) -> str:
        """Read a built-in template file by name."""
        return TEMPLATES.joinpath(name).read_text()

    @staticmethod
    def _write_template(dest: Path, content: str) -> None:
        """Write *content* to *dest* if it does not already exist."""
        if dest.exists():
            return
        dest.write_text(content)
        logger.info("Created %s", dest)
