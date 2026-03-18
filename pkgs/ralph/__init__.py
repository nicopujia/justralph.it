"""Ralph: An autonomous agent that processes Beads issues using OpenCode.

This package provides the core functionality for Ralph, an autonomous agent
that claims, processes, and completes issues from a Beads issue tracker.

Main modules:
    agent: OpenCode agent wrapper with status tracking
    loop: Main control loop with crash recovery
    config: CLI configuration and runtime settings
    state: State persistence for crash recovery
    git: Git branch and repository management
    hooks: User-customizable hooks for extending Ralph
    init: Ralph environment initialization

Usage:
    python -m ralph.loop [--model MODEL] [--max-iters N]
"""
