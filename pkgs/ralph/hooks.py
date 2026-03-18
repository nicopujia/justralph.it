"""Base class for Ralph lifecycle hooks.

Subclass Hooks in .ralph/hooks.py and override only the methods you need.
The loop instantiates the subclass once and calls its methods at the
appropriate points in the execution lifecycle.
"""

from abc import ABC, abstractmethod
from typing import Any

from bd import Issue

from .agent import Agent
from .config import Config


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
