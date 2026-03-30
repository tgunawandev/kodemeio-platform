"""Exception hierarchy -- re-exported from kctl-common."""

from kctl_common.exceptions import (
    APIError,
    AuthenticationError,
    CommandError,
    ConfigError,
    KctlError,
    NotFoundError,
)
from kctl_common.exceptions import ConnectionError as KctlConnectionError

__all__ = [
    "APIError",
    "AuthenticationError",
    "CommandError",
    "ConfigError",
    "KctlConnectionError",
    "KctlError",
    "NotFoundError",
]
