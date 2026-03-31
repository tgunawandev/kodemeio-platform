"""Exception hierarchy — re-exported from kctl-lib."""

from kctl_lib.exceptions import (
    APIError,
    AuthenticationError,
    CommandError,
    ConfigError,
    ConnectionError,
    KctlError,
    NotFoundError,
)

__all__ = [
    "APIError",
    "AuthenticationError",
    "CommandError",
    "ConfigError",
    "ConnectionError",
    "KctlError",
    "NotFoundError",
]
