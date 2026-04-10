"""Custom exception hierarchy for kctl-outline.

# KCTL-COMMON: extractable
"""

from __future__ import annotations

import httpx


class KctlError(Exception):
    """Base exception for all kctl errors."""


class ConfigError(KctlError):
    """Configuration-related errors."""


class AuthenticationError(KctlError):
    """Authentication/token errors."""


class NotFoundError(KctlError):
    """Resource not found."""

    def __init__(self, resource_type: str, identifier: str):
        self.resource_type = resource_type
        self.identifier = identifier
        super().__init__(f"{resource_type} not found: {identifier}")


class APIError(KctlError):
    """Outline API error with response details."""

    def __init__(self, response: httpx.Response):
        self.status_code = response.status_code
        self.response = response
        try:
            body = response.json()
            self.detail = body.get("message", body.get("error", str(body)))
        except Exception:
            self.detail = response.text or f"HTTP {self.status_code}"
        super().__init__(f"API error {self.status_code}: {self.detail}")


class ConnectionError(KctlError):
    """Cannot connect to Outline."""

    def __init__(self, url: str, cause: Exception | None = None):
        self.url = url
        self.cause = cause
        super().__init__(f"Cannot connect to {url}: {cause}")
