"""Exception hierarchy — re-exported from kctl-common."""

from kctl_common.exceptions import (
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
