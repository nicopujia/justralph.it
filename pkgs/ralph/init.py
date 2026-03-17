"""Scaffold a .ralph/ directory in the current project."""

import importlib.util
import logging
import sys
from types import ModuleType

from .config import Config
from .hooks import Hooks

logger = logging.getLogger(__name__)

DEFAULT_HOOKS = '''\
"""Ralph lifecycle hooks.

Override methods to customise behaviour.
Run `python -c "from ralph.hooks import Hooks; help(Hooks)"` to see the full interface.
"""

from ralph.hooks import Hooks


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


def init_ralph_dir(cfg: Config) -> None:
    """Create .ralph/ and scaffold default files if they don't exist."""
    cfg.base_dir.mkdir(parents=True, exist_ok=True)
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)

    hooks_file = cfg.base_dir / "hooks.py"
    if not hooks_file.exists():
        hooks_file.write_text(DEFAULT_HOOKS)
        logger.info("Created %s", hooks_file)

    if not cfg.notes_file.exists():
        cfg.notes_file.write_text("")
        logger.info("Created %s", cfg.notes_file)

    gitignore_file = cfg.base_dir / ".gitignore"
    if not gitignore_file.exists():
        gitignore_file.write_text("logs/\nstate.json\n*.ralph\n")
        logger.info("Created %s", gitignore_file)


def load_hooks(cfg: Config) -> Hooks:
    """Dynamically import CustomHooks from .ralph/hooks.py."""
    hooks_file = cfg.base_dir / "hooks.py"
    if not hooks_file.exists():
        raise FileNotFoundError(
            f"{hooks_file} not found. Run `ralph` from a project directory "
            f"or run `ralph init` first."
        )

    spec = importlib.util.spec_from_file_location("_ralph_hooks", hooks_file)
    assert spec and spec.loader
    module: ModuleType = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    hooks_cls = getattr(module, "CustomHooks", None)
    if hooks_cls is None:
        raise AttributeError(f"{hooks_file} must define a CustomHooks class")
    if not issubclass(hooks_cls, Hooks):
        raise TypeError(f"CustomHooks in {hooks_file} must subclass ralph.hooks.Hooks")

    return hooks_cls()
