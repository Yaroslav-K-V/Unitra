class UnitraError(Exception):
    """Base exception for application-level failures."""


class ValidationError(UnitraError):
    """Raised when user input cannot be processed."""


class DependencyError(UnitraError):
    """Raised when an external dependency is unavailable."""
