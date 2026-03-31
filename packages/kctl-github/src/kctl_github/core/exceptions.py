"""Exception hierarchy -- re-exported from kctl-lib."""

from kctl_lib.exceptions import (
    APIError,
    AuthenticationError,
    CommandError,
    ConfigError,
    KctlError,
    NotFoundError,
)
from kctl_lib.exceptions import ConnectionError as KctlConnectionError

__all__ = [
    "APIError",
    "AuthenticationError",
    "CommandError",
    "ConfigError",
    "KctlConnectionError",
    "KctlError",
    "NotFoundError",
]
