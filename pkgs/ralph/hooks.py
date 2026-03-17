"""Base class for Ralph lifecycle hooks.

Subclass ``Hooks`` in ``var/hooks.py`` and override only the methods you
need.  The loop instantiates the subclass once and calls its methods at
the appropriate points.
"""

from abc import ABC, abstractmethod
from typing import Any

from bd import Issue

from .agent import Agent
from .config import Config


class Hooks(ABC):
    """Hook interface -- subclass and override to customise behaviour."""

    @abstractmethod
    def pre_loop(self, cfg: Config) -> None:
        """Called once before the loop starts."""

    @abstractmethod
    def pre_iter(self, cfg: Config, issue: Issue, iteration: int) -> None:
        """Called before each iteration."""

    @abstractmethod
    def post_iter(
        self,
        cfg: Config,
        issue: Issue,
        iteration: int,
        status: Agent.Status,
        error: Exception | None,
    ) -> None:
        """Called after each iteration.

        *status* is the ``Agent.Status`` the run ended with.
        *error* is the exception if one occurred, otherwise ``None``.
        """

    @abstractmethod
    def post_loop(self, cfg: Config, iterations_completed: int) -> None:
        """Called once after the loop finishes."""

    @abstractmethod
    def extra_args_kwargs(
        self, cfg: Config, issue: Issue
    ) -> tuple[tuple, dict[str, Any]]:
        """Return extra positional/keyword args forwarded to the Agent."""
