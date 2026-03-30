"""Exception hierarchy for kctl-gatus — re-exports from kctl-common."""

from __future__ import annotations

from kctl_common.exceptions import (
    APIError,
    AuthenticationError,
    ConfigError,
    ConnectionError,
    KctlError,
    NotFoundError,
    ValidationError,
)

__all__ = [
    "APIError",
    "AuthenticationError",
    "ConfigError",
    "ConnectionError",
    "KctlError",
    "NotFoundError",
    "ValidationError",
]
