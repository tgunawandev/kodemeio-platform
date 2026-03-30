"""Exception hierarchy for kctl-pg.

Re-exports common exceptions from kctl-common, plus DB-specific ones.
"""

from __future__ import annotations

# Re-export shared exceptions from kctl-common
from kctl_common.exceptions import (
    AuthenticationError,
    ConfigError,
    KctlError,
    NotFoundError,
)
from kctl_common.exceptions import ConnectionError as KctlConnectionError

__all__ = [
    "AuthenticationError",
    "ConfigError",
    "DatabaseError",
    "KctlConnectionError",
    "KctlError",
    "NotFoundError",
    "SSHTunnelError",
]


class DatabaseError(KctlError):
    """SQL / database operation error."""

    def __init__(self, message: str, query: str | None = None):
        self.query = query
        super().__init__(message)


class SSHTunnelError(KctlError):
    """SSH tunnel establishment failed."""

    def __init__(self, ssh_host: str, cause: Exception | None = None):
        self.ssh_host = ssh_host
        self.cause = cause
        super().__init__(f"SSH tunnel to {ssh_host} failed: {cause}")
