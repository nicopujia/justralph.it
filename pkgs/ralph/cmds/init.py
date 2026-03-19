"""Scaffold a Ralph project directory."""

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import ralph as ralph_module

from ..config import Config
from ..utils.git import (
    add_worktree,
    convert_to_bare,
    has_worktree,
    init_bare,
    is_repo,
    reset_branch,
)
from . import Command

logger = logging.getLogger(__name__)

# Get path to Ralph's installation templates (works for any install type)
TEMPLATES = Path(ralph_module.__file__).parent / "templates"


@dataclass
class InitConfig(Config):
    """Configuration for the init command."""

    force: bool = field(
        default=False,
        metadata={"help": "Delete and re-create the project directory"},
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
                opencode.jsonc -> /path/to/ralph/templates/opencode.jsonc
                PROMPT.xml -> /path/to/ralph/templates/PROMPT.xml
                prod/            # worktree on main
                ├── .ralph/      # ralph config, state, and logs
                │   ├── hooks.py
                │   ├── .gitignore
                │   ├── logs/
                │   └── state.json
                └── ...          # other project files
                dev/             # worktree on dev

        The opencode.jsonc and PROMPT.xml files are symlinked to Ralph's
        installation templates. This ensures projects always use the latest
        versions and updates are applied automatically when Ralph is upgraded.
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
        
        # Symlink templates from Ralph's installation (auto-updates with Ralph)
        self._symlink_template(root, "opencode.jsonc")
        self._symlink_template(root, "PROMPT.xml")
        # AGENTS.md can be anywhere in the repo - user creates it manually

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
        else:
            # Ensure dev branch is synced with main
            reset_branch(root, "dev", "main")

    # -- ralph config files ------------------------------------------------

    def _scaffold_ralph_dir(self, root: Path) -> None:
        """Create prod/.ralph/ with hooks, .gitignore, logs dir, and runtime files."""
        ralph_dir = root / "prod" / ".ralph"
        ralph_dir.mkdir(parents=True, exist_ok=True)
        (ralph_dir / "logs").mkdir(parents=True, exist_ok=True)
        
        # Write template files to prod/.ralph/
        hooks_path = ralph_dir / "hooks.py"
        if not hooks_path.exists():
            hooks_path.write_text(self._read_template("hooks.py"))
            logger.info("Created %s", hooks_path)
        
        gitignore_path = ralph_dir / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text("logs/\nstate.json\n*.ralph\n")
            logger.info("Created %s", gitignore_path)

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _read_template(name: str) -> str:
        """Read a built-in template file by name."""
        return (TEMPLATES / name).read_text()

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

    @staticmethod
    def _symlink_template(root: Path, filename: str) -> None:
        """Create symlink from project root to Ralph's template.
        
        Args:
            root: Project root directory
            filename: Template file name (e.g., "opencode.jsonc")
        """
        symlink_path = root / filename
        template_path = TEMPLATES / filename
        
        # Create or update symlink at root
        if symlink_path.exists() or symlink_path.is_symlink():
            symlink_path.unlink()
        symlink_path.symlink_to(template_path)
        logger.info("Created symlink %s -> %s (Ralph template)", symlink_path, template_path)
