"""Exception hierarchy for kctl-api — thin re-exports from kctl-common.

APIError is kept locally because it wraps httpx.Response.
"""

from __future__ import annotations

import httpx
from kctl_common.exceptions import (
    AuthenticationError,
    ConfigError,
    ConnectionError,
    KctlError,
    NotFoundError,
)

__all__ = [
    "APIError",
    "AuthenticationError",
    "ConfigError",
    "ConnectionError",
    "KctlError",
    "NotFoundError",
]


class APIError(KctlError):
    """REST API error with response details."""

    def __init__(self, response: httpx.Response | None = None, detail: str = ""):
        if response is not None:
            self.status_code = response.status_code
            self.response = response
            try:
                body = response.json()
                self.detail = body.get("error", "") or body.get("detail", "") or str(body)
            except Exception:
                self.detail = response.text or f"HTTP {self.status_code}"
        else:
            self.status_code = 0
            self.response = None
            self.detail = detail
        super().__init__(f"API error: {self.detail}")
