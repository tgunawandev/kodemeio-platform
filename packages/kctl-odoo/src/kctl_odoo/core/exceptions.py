"""Exception hierarchy — re-exported from kctl-common, with Odoo-specific additions."""

from __future__ import annotations

import httpx
from kctl_common.exceptions import (
    AuthenticationError,
    CommandError,
    ConfigError,
    ConnectionError,
    KctlError,
    NotFoundError,
)

__all__ = [
    "APIError",
    "AuthenticationError",
    "CommandError",
    "ConfigError",
    "ConnectionError",
    "KctlError",
    "NotFoundError",
    "RPCError",
]


class APIError(KctlError):
    """Odoo JSON-RPC error with httpx response details."""

    def __init__(self, response: httpx.Response | None = None, detail: str = ""):
        if response is not None:
            self.status_code = response.status_code
            self.response = response
            try:
                body = response.json()
                error = body.get("error", {})
                self.detail = error.get("message", "") or error.get("data", {}).get("message", "") or str(body)
            except Exception:
                self.detail = response.text or f"HTTP {self.status_code}"
        else:
            self.status_code = 0
            self.response = None
            self.detail = detail
        super().__init__(f"API error: {self.detail}")


class RPCError(KctlError):
    """Odoo JSON-RPC level error (error in response body)."""

    def __init__(self, error_data: dict):
        self.error_data = error_data
        message = error_data.get("message", "")
        data = error_data.get("data", {})
        debug = data.get("message", "") or data.get("debug", "")
        self.detail = f"{message}: {debug}" if debug else message
        super().__init__(self.detail)
