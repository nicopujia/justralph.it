"""Subprocess environment helper — ensures PATH includes user-local bin directories."""

import os


# Directories that must be on PATH for subprocess calls (bd, bdui, opencode, etc.)
_EXTRA_PATH_DIRS = [
    os.path.expanduser("~/.local/bin"),
    os.path.expanduser("~/.npm-global/bin"),
]


def subprocess_env(**extra: str) -> dict[str, str]:
    """Return an env dict suitable for subprocess calls.

    Prepends ~/.local/bin and ~/.npm-global/bin to PATH so that tools like
    bd, bdui, and opencode are found even when the web app is started from
    a restricted environment (e.g. systemd).

    Any keyword arguments are merged into the result, overriding os.environ.
    """
    env = os.environ.copy()
    current_path = env.get("PATH", "")
    dirs_to_add = [d for d in _EXTRA_PATH_DIRS if d not in current_path.split(os.pathsep)]
    if dirs_to_add:
        env["PATH"] = os.pathsep.join(dirs_to_add + [current_path])
    env.update(extra)
    return env
