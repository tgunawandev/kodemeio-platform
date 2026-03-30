"""Exception hierarchy — re-exported from kctl-common."""

from kctl_common.exceptions import (
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
