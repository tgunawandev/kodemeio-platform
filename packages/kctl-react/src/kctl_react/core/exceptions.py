"""Exception hierarchy — re-exported from kctl-lib."""

from kctl_lib.exceptions import (
    AppNotFoundError,
    CommandError,
    ConfigError,
    KctlError,
    NotFoundError,
)

__all__ = [
    "AppNotFoundError",
    "CommandError",
    "ConfigError",
    "KctlError",
    "NotFoundError",
]
