"""Command interface. See AGENTS.md in this directory for the full protocol."""

import argparse
from abc import ABC, abstractmethod

from ..config import Config


class Command(ABC):
    """Base class every CLI command must subclass.

    The command name is inferred from the module filename.
    ``cfg`` is set by the CLI before ``run()`` is called.
    """

    help: str  # one-line description for --help
    config: type[Config] = Config  # override with a Config subclass for extra flags
    cfg: Config  # populated by main.py before run()

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        """Called after auto-generated flags are added. Override to add aliases."""

    @abstractmethod
    def run(self) -> None: ...
