"""Base class for Ralph lifecycle hooks.

Subclass Hooks in .ralph/hooks.py and override only the methods you need.
The loop instantiates the subclass once and calls its methods at the
appropriate points in the execution lifecycle.
"""

import importlib.util
import logging
import sys
from abc import ABC, abstractmethod
from types import ModuleType
from typing import Any

from bd import Issue

from ..config import Config
from .agent import Agent

logger = logging.getLogger(__name__)


class Hooks(ABC):
    """Hook interface for customizing Ralph's lifecycle behavior.

    Subclass this in .ralph/hooks.py and override methods to extend or
    modify Ralph's behavior at key points in the execution lifecycle.
    """

    @abstractmethod
    def pre_loop(self, cfg: Config) -> None:
        """Run once before the main loop starts.

        Args:
            cfg: Runtime configuration
        """

    @abstractmethod
    def pre_iter(self, cfg: Config, issue: Issue, iteration: int) -> None:
        """Run before each iteration.

        Args:
            cfg: Runtime configuration
            issue: The issue about to be processed
            iteration: Current iteration index
        """

    @abstractmethod
    def post_iter(
        self,
        cfg: Config,
        issue: Issue,
        iteration: int,
        status: Agent.Status,
        error: Exception | None,
    ) -> None:
        """Run after each iteration completes or fails.

        Args:
            cfg: Runtime configuration
            issue: The issue that was processed
            iteration: Current iteration index
            status: Final Agent.Status from the run
            error: Exception if one occurred, otherwise None
        """

    @abstractmethod
    def post_loop(self, cfg: Config, iterations_completed: int) -> None:
        """Run once after the main loop finishes.

        Args:
            cfg: Runtime configuration
            iterations_completed: Total number of iterations executed
        """

    @abstractmethod
    def extra_args_kwargs(
        self, cfg: Config, issue: Issue
    ) -> tuple[tuple, dict[str, Any]]:
        """Return extra arguments to pass to the Agent constructor.

        Args:
            cfg: Runtime configuration
            issue: The issue about to be processed

        Returns:
            Tuple of (positional_args, keyword_args) forwarded to Agent
        """


def load_hooks(cfg: Config) -> Hooks:
    """Dynamically import and instantiate CustomHooks from prod/.ralph/hooks.py.

    Args:
        cfg: Runtime configuration with base_dir path

    Returns:
        Instance of CustomHooks class

    Raises:
        FileNotFoundError: If prod/.ralph/hooks.py does not exist
        AttributeError: If CustomHooks class is not defined
        TypeError: If CustomHooks does not subclass Hooks
    """
    hooks_file = cfg.base_dir / "prod" / ".ralph" / "hooks.py"
    if not hooks_file.exists():
        raise FileNotFoundError(f"{hooks_file} not found. Run `ralph init` first.")

    spec = importlib.util.spec_from_file_location("_ralph_hooks", hooks_file)
    assert spec and spec.loader
    module: ModuleType = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    hooks_cls = getattr(module, "CustomHooks", None)
    if hooks_cls is None:
        raise AttributeError(f"{hooks_file} must define a CustomHooks class")
    if not issubclass(hooks_cls, Hooks):
        raise TypeError(
            f"CustomHooks in {hooks_file} must subclass ralph.core.hooks.Hooks"
        )

    return hooks_cls()
