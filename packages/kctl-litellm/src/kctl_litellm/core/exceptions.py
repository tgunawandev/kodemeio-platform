"""Exception hierarchy for kctl-litellm.

Re-exports common exceptions from kctl-lib, plus LiteLLM-specific ones.
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
    "KctlError",
    "LiteLLMError",
    "NotFoundError",
]


class LiteLLMError(KctlError):
    """Base error for LiteLLM operations."""


class ConnectionError(LiteLLMError):  # noqa: A001
    """Cannot connect to LiteLLM at {host}: {cause}"""

    def __init__(self, host: str, cause: Exception | None = None):
        self.host = host
        self.cause = cause
        super().__init__(f"Cannot connect to LiteLLM at {host}: {cause}")


class AuthError(LiteLLMError):
    """Authentication/authorization error."""


class APIError(LiteLLMError):
    """API error {status_code} on {endpoint}: {message}"""

    def __init__(self, status_code: int, endpoint: str, message: str = ""):
        self.status_code = status_code
        self.endpoint = endpoint
        super().__init__(f"API error {status_code} on {endpoint}: {message}")
