"""Scaffold the .ralph/ directory."""

import logging
import shutil
from dataclasses import dataclass, field

from ..config import Config
from . import Command

logger = logging.getLogger(__name__)

DEFAULT_HOOKS = '''\
"""Ralph lifecycle hooks.

Override methods to customise behaviour.
Run `python -c "from ralph.core.hooks import Hooks; help(Hooks)"` to see the full interface.
"""

from ralph.core.hooks import Hooks


class CustomHooks(Hooks):
    def pre_loop(self, cfg):
        pass

    def pre_iter(self, cfg, issue, iteration):
        pass

    def post_iter(self, cfg, issue, iteration, status, error):
        pass

    def post_loop(self, cfg, iterations_completed):
        pass

    def extra_args_kwargs(self, cfg, issue):
        return (), {}
'''


@dataclass
class InitConfig(Config):
    """Configuration for the init command."""

    force: bool = field(
        default=False,
        metadata={"help": "Delete and re-create the .ralph/ directory"},
    )


class Init(Command):
    help = "Scaffold the .ralph/ directory"
    config = InitConfig
    cfg: InitConfig

    def run(self) -> None:
        """Create .ralph/ and its default files.

        Creates base_dir, logs_dir, a default hooks.py, and a .gitignore.
        Safe to re-run; existing files are not overwritten unless --force
        is given, which deletes the entire directory first.
        """
        cfg = self.cfg

        if cfg.force and cfg.base_dir.exists():
            shutil.rmtree(cfg.base_dir)
            logger.info("Removed %s", cfg.base_dir)

        cfg.base_dir.mkdir(parents=True, exist_ok=True)
        (cfg.base_dir / "logs").mkdir(parents=True, exist_ok=True)

        hooks_file = cfg.base_dir / "hooks.py"
        if not hooks_file.exists():
            hooks_file.write_text(DEFAULT_HOOKS)
            logger.info("Created %s", hooks_file)

        gitignore = cfg.base_dir / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text("logs/\nstate.json\n*.ralph\n")
            logger.info("Created %s", gitignore)

        logger.info("Initialized %s", cfg.base_dir)
