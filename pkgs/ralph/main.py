"""Ralph CLI entry point."""

import argparse
import importlib
import logging
import pkgutil
from pathlib import Path

from . import cmds
from .cmds import Command
from .config import Config, get_fields

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


def main() -> None:
    """Parse CLI args and dispatch to the matching command."""
    commands = _discover_commands()

    parser = argparse.ArgumentParser(prog="ralph", description="Ralph CLI")
    _add_fields(parser, Config)

    sub = parser.add_subparsers(dest="command")
    for name, cmd in commands.items():
        cmd_parser = sub.add_parser(name, help=cmd.help)
        _add_fields(cmd_parser, cmd.config)
        cmd.configure_parser(cmd_parser)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        raise SystemExit(1)

    cmd = commands[args.command]
    cmd.cfg = cmd.config(**{k: v for k, v in vars(args).items() if k != "command"})

    log_level = getattr(logging, cmd.cfg.log_level.upper(), logging.INFO)
    logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATEFMT, level=log_level)

    cmd.run()


def _discover_commands() -> dict[str, Command]:
    """Import every module in ``ralph.cmds`` and return {name: instance}."""
    result: dict[str, Command] = {}
    for info in pkgutil.iter_modules(cmds.__path__, cmds.__name__ + "."):
        mod = importlib.import_module(info.name)
        cmd_name = info.name.rsplit(".", 1)[-1]
        for obj in vars(mod).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, Command)
                and obj is not Command
            ):
                result[cmd_name] = obj()
    return result


def _add_fields(
    parser: argparse.ArgumentParser,
    cfg_cls: type[Config],
) -> None:
    """Add ``--flags`` to *parser* derived from *cfg_cls* fields."""
    for f, flag, default in get_fields(cfg_cls):
        kw: dict = {"help": f.metadata["help"]}
        if f.type is bool:
            kw["action"] = "store_true"
            kw["default"] = default
        else:
            kw["type"] = f.type if f.type is not Path else Path
            kw["default"] = default
            kw["help"] += f" (default: {default})"
        if "choices" in f.metadata:
            kw["choices"] = f.metadata["choices"]
        parser.add_argument(flag, **kw)


if __name__ == "__main__":
    main()
