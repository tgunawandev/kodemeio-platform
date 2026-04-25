"""Exception hierarchy for kctl-supa.

Re-exports common exceptions from kctl-lib, plus Supabase-specific ones.
"""

from __future__ import annotations

# Re-export shared exceptions from kctl-lib
from kctl_lib.exceptions import (
    AuthenticationError,
    ConfigError,
    KctlError,
    NotFoundError,
)

__all__ = [
    "APIError",
    "AuthError",
    "AuthenticationError",
    "ConfigError",
    "ConnectionError",
    "DockerError",
    "KctlError",
    "NotFoundError",
    "SupabaseError",
]


class SupabaseError(KctlError):
    """Base error for Supabase operations."""


class ConnectionError(SupabaseError):  # noqa: A001
    """Cannot connect to Supabase at {host}: {cause}"""

    def __init__(self, host: str, cause: Exception | None = None):
        self.host = host
        self.cause = cause
        super().__init__(f"Cannot connect to Supabase at {host}: {cause}")


class AuthError(SupabaseError):
    """Authentication/authorization error."""


class APIError(SupabaseError):
    """API error {status_code} on {endpoint}: {message}"""

    def __init__(self, status_code: int, endpoint: str, message: str = ""):
        self.status_code = status_code
        self.endpoint = endpoint
        super().__init__(f"API error {status_code} on {endpoint}: {message}")


class DockerError(SupabaseError):
    """Docker/SSH operation failed."""
