"""Exception hierarchy for kctl-hetzner.

Re-exports from kctl-common with Hetzner-specific aliases.
"""

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
