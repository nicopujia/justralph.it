"""Ralph: An autonomous coding agent loop powered by ralphy.

Package layout:
    config:         Single source of truth for all configuration and defaults
    main:           CLI entry point (argparse with subcommands)
    cmds/:          One module per CLI command (init, loop, run, task)
    core/:          Core business logic (agent, hooks, state, ralphy_runner, events)
    utils/:         Shared utilities (git, backup)
    templates/:     Scaffolding skeletons copied into new projects
    PROMPT.xml:     System prompt for the Ralph agent (symlinked into projects)
"""
