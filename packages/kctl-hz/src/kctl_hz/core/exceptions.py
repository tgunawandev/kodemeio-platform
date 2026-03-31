"""Exception hierarchy for kctl-hz.

Re-exports from kctl-lib with Hetzner-specific aliases.
"""

from __future__ import annotations

from kctl_lib.exceptions import (
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
