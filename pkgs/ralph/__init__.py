"""Ralph: An autonomous agent that processes Beads issues using OpenCode.

This package provides the core functionality for Ralph, an autonomous agent
that claims, processes, and completes issues from a Beads issue tracker.

Package layout:
    config: Single source of truth for all configuration and defaults
    main:   CLI entry point (argparse with subcommands)
    cmds/:  One module per CLI command (init, loop)
    lib/:   Core business logic (agent, git, hooks, init, loop, state)

Usage:
    ralph init              # scaffold .ralph/ directory
    ralph loop [--flags]    # run the main agent loop
"""
