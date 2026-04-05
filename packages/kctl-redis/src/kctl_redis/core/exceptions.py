"""Exception hierarchy for kctl-redis.

Re-exports common exceptions from kctl-lib, plus Redis-specific ones.
"""

from __future__ import annotations

from kctl_lib.exceptions import (
    AuthenticationError,
    ConfigError,
    KctlError,
    NotFoundError,
)
from kctl_lib.exceptions import ConnectionError as KctlConnectionError

__all__ = [
    "AuthenticationError",
    "ConfigError",
    "KctlConnectionError",
    "KctlError",
    "NotFoundError",
    "RedisCommandError",
    "SSHTunnelError",
]


class RedisCommandError(KctlError):
    """Redis command execution error."""

    def __init__(self, message: str, command: str | None = None):
        self.command = command
        super().__init__(message)


class SSHTunnelError(KctlError):
    """SSH tunnel establishment failed."""

    def __init__(self, ssh_host: str, cause: Exception | None = None):
        self.ssh_host = ssh_host
        self.cause = cause
        super().__init__(f"SSH tunnel to {ssh_host} failed: {cause}")
