"""Exception hierarchy for kctl-dokploy.

Re-exports from kctl-lib with service-specific additions.
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
    "DeploymentError",
    "HealthCheckError",
    "KctlError",
    "NotFoundError",
    "NotificationError",
    "TimeoutError",
    "ValidationError",
]


# Service-specific exceptions, inheriting from kctl-lib bases


class TimeoutError(ConnectionError):
    """Request timeout error."""

    def __init__(self, url: str, timeout: float):
        self.url = url
        self.timeout = timeout
        # ConnectionError expects (url, cause) but we override the message
        super().__init__(url, None)
        self.args = (f"Request to {url} timed out after {timeout}s",)


class DeploymentError(KctlError):
    """Deployment pipeline error."""


class HealthCheckError(KctlError):
    """Health check failure."""


class NotificationError(KctlError):
    """Notification dispatch error."""
