"""Exception hierarchy for kctl-cloudflare — re-exported from kctl-common."""

from kctl_common.exceptions import (
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
