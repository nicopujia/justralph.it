"""Ralph CLI entry point.

Usage::

    ralph init          # scaffold the .ralph/ directory
    ralph loop          # run the main agent loop (requires init first)
    ralph loop --help   # show loop-specific options
"""

import argparse
from pathlib import Path

from .cmds import init, loop
from .config import Config, get_fields


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level parser with subcommands.

    Flags are derived automatically from :class:`Config` field metadata so
    config and its documentation live in a single place.
    """
    parser = argparse.ArgumentParser(prog="ralph", description="Ralph CLI")

    # ── Global flags (shared across all subcommands) ─────────────────────
    global_names = {"base_dir", "log_level"}
    for f, flag, default in get_fields():
        if f.name not in global_names:
            continue
        kw: dict = {
            "type": f.type if f.type is not Path else Path,
            "default": default,
            "help": f"{f.metadata['help']} (default: {default})",
        }
        if "choices" in f.metadata:
            kw["choices"] = f.metadata["choices"]
        parser.add_argument(flag, **kw)

    # ── Subcommands ──────────────────────────────────────────────────────
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="Scaffold the .ralph/ directory")

    loop_parser = sub.add_parser("loop", help="Run the main agent loop")
    loop_only = {f.name for f, _, _ in get_fields()} - global_names
    for f, flag, default in get_fields():
        if f.name not in loop_only:
            continue
        kw = {
            "type": f.type if f.type is not Path else Path,
            "default": default,
            "help": f"{f.metadata['help']} (default: {default})",
        }
        if "choices" in f.metadata:
            kw["choices"] = f.metadata["choices"]
        loop_parser.add_argument(flag, **kw)

    return parser


def main() -> None:
    """Parse CLI args and dispatch to the appropriate command."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        raise SystemExit(1)

    cfg = Config(**{k: v for k, v in vars(args).items() if k != "command"})

    match args.command:
        case "init":
            init.run(cfg)
        case "loop":
            loop.run(cfg)


if __name__ == "__main__":
    main()
