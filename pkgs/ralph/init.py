"""Ralph environment initialization and hooks loading."""

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
    """Create .ralph/ directory and scaffold default files if missing.

    Creates:
        - .ralph/ base directory
        - .ralph/logs/ directory
        - .ralph/hooks.py with default CustomHooks template
        - .ralph/.gitignore to ignore logs and state files

    Args:
        cfg: Runtime configuration with directory paths
    """
    cfg.base_dir.mkdir(parents=True, exist_ok=True)
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)

    hooks_file = cfg.base_dir / "hooks.py"
    if not hooks_file.exists():
        hooks_file.write_text(DEFAULT_HOOKS)
        logger.info("Created %s", hooks_file)

    gitignore_file = cfg.base_dir / ".gitignore"
    if not gitignore_file.exists():
        gitignore_file.write_text("logs/\nstate.json\n*.ralph\n")
        logger.info("Created %s", gitignore_file)


def load_hooks(cfg: Config) -> Hooks:
    """Dynamically import and instantiate CustomHooks from .ralph/hooks.py.

    Args:
        cfg: Runtime configuration with base_dir path

    Returns:
        Instance of CustomHooks class

    Raises:
        FileNotFoundError: If .ralph/hooks.py does not exist
        AttributeError: If CustomHooks class is not defined
        TypeError: If CustomHooks does not subclass ralph.hooks.Hooks
    """
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
