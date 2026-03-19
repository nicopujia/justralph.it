"""Scaffold the .ralph/ directory."""

import logging

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


class Init(Command):
    help = "Scaffold the .ralph/ directory"

    def run(self) -> None:
        """Create .ralph/ and its default files.

        Creates base_dir, logs_dir, a default hooks.py, and a .gitignore.
        Safe to re-run; existing files are not overwritten.
        """
        cfg = self.cfg

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
