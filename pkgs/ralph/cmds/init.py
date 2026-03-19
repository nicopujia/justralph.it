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
                .ralph/          # ralph state (logs/, state.json - runtime)
                ├── hooks.py -> prod/.ralph/hooks.py
                └── .gitignore -> prod/.ralph/.gitignore
                AGENTS.md -> prod/AGENTS.md
                opencode.jsonc -> prod/opencode.jsonc
                PROMPT.xml -> prod/PROMPT.xml
                prod/            # worktree on main
                ├── .ralph/      # tracked ralph config
                │   ├── hooks.py
                │   └── .gitignore
                ├── AGENTS.md
                ├── opencode.jsonc
                └── PROMPT.xml
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
        
        # Project config files live in prod/ worktree, symlinked to root for convenience
        self._symlink_to_worktree(root, "prod", "AGENTS.md", self._agents_md_content())
        self._symlink_to_worktree(root, "prod", "opencode.jsonc", self._read_template("opencode.jsonc"))
        self._symlink_to_worktree(root, "prod", "PROMPT.xml", self._read_template("PROMPT.xml"))

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
        """Create .ralph/ at root (runtime) and prod/.ralph/ (tracked) with symlinks."""
        # Runtime directory at root (logs, state - not tracked)
        ralph_dir = root / ".ralph"
        ralph_dir.mkdir(parents=True, exist_ok=True)
        (ralph_dir / "logs").mkdir(parents=True, exist_ok=True)
        
        # Tracked config in prod/.ralph/ with symlinks to root
        self._symlink_to_worktree(root, "prod", ".ralph/hooks.py", self._read_template("hooks.py"))
        self._symlink_to_worktree(root, "prod", ".ralph/.gitignore", "logs/\nstate.json\n*.ralph\n")

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

    @staticmethod
    def _symlink_to_worktree(root: Path, worktree: str, filename: str, content: str) -> None:
        """Write file to worktree and create symlink at root.
        
        Args:
            root: Project root directory
            worktree: Worktree name (e.g., "prod", "dev")
            filename: File path relative to worktree (e.g., "AGENTS.md" or ".ralph/hooks.py")
            content: File content to write
        """
        worktree_path = root / worktree / filename
        symlink_path = root / filename
        
        # Ensure parent directories exist in worktree
        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file in worktree if it doesn't exist
        if not worktree_path.exists():
            worktree_path.write_text(content)
            logger.info("Created %s", worktree_path)
        
        # Ensure parent directories exist at root for the symlink
        symlink_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create or update symlink at root
        if symlink_path.exists() or symlink_path.is_symlink():
            symlink_path.unlink()
        symlink_path.symlink_to(worktree_path.relative_to(root))
        logger.info("Created symlink %s -> %s", symlink_path, worktree_path)
