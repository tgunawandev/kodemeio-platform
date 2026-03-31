"""Custom exception hierarchy for kctl-claw.

Thin re-exports from kctl-lib where compatible.
Claw-specific exceptions (GatewayError, NotFoundError) are kept locally.
"""

from __future__ import annotations

from kctl_lib.exceptions import ConfigError, DockerError, KctlError, ValidationError

__all__ = [
    "ConfigError",
    "DockerError",
    "GatewayError",
    "KctlError",
    "NotFoundError",
    "ValidationError",
]


class GatewayError(KctlError):
    """OpenClaw gateway HTTP API errors."""

    def __init__(self, status_code: int = 0, message: str = ""):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Gateway error ({status_code}): {message}" if status_code else message)


class NotFoundError(KctlError):
    """Resource not found (agent, cron job, MCP server, skill)."""

    def __init__(self, resource_type: str, identifier: str, valid_names: list[str] | None = None):
        self.resource_type = resource_type
        self.identifier = identifier
        self.valid_names = valid_names or []
        hint = f" (valid: {', '.join(self.valid_names)})" if self.valid_names else ""
        super().__init__(f"{resource_type} not found: {identifier}{hint}")
