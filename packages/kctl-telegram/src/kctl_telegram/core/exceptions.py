"""Exception hierarchy for kctl-telegram.

Re-exports from kctl-lib with service-specific aliases.
"""

from __future__ import annotations

from kctl_lib.exceptions import (
    APIError,
    AuthenticationError,
    CommandError,
    ConfigError,
    ConnectionError,
    DockerError,
    KctlError,
    NotFoundError,
    ValidationError,
)

__all__ = [
    "APIError",
    "AuthenticationError",
    "CommandError",
    "ConfigError",
    "ConnectionError",
    "DockerError",
    "KctlError",
    "NotFoundError",
    "ValidationError",
]
