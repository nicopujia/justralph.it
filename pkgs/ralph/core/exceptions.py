"""Ralph exceptions."""


class StopRequested(Exception):
    """Raised when a stop signal is detected."""


class RestartRequested(Exception):
    """Raised when a restart signal is detected."""


class BadAgentStatus(ValueError):
    """Raised when the agent's status XML is missing, unparseable, or invalid."""
