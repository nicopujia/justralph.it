"""Ralph: An autonomous agent that processes Beads issues using OpenCode.

Package layout:
    config:         Single source of truth for all configuration and defaults
    main:           CLI entry point (argparse with subcommands)
    cmds/:          One module per CLI command (init, loop)
    core/:          Core business logic (agent, hooks, state)
    utils/:         Shared utilities (git)
    templates/:     Scaffolding skeletons copied into new projects
    opencode.jsonc: OpenCode agent config (symlinked into projects)
    PROMPT.xml:     System prompt for the Ralph agent (symlinked into projects)
"""
