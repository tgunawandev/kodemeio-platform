"""Unified exception hierarchy for all kctl-* CLI tools."""

from __future__ import annotations


class KctlError(Exception):
    """Base exception for all kctl errors."""


class ConfigError(KctlError):
    """Configuration-related errors."""


class AuthenticationError(KctlError):
    """Authentication/API key errors."""


class NotFoundError(KctlError):
    """Resource not found."""

    def __init__(self, resource_type: str, identifier: str):
        self.resource_type = resource_type
        self.identifier = identifier
        super().__init__(f"{resource_type} not found: {identifier}")


class AppNotFoundError(NotFoundError):
    """App not found in monorepo."""

    def __init__(self, app_name: str, valid_apps: list[str] | None = None):
        self.valid_apps = valid_apps or []
        super().__init__("app", app_name)

    def __str__(self) -> str:
        hint = f" (valid: {', '.join(self.valid_apps)})" if self.valid_apps else ""
        return f"App not found: {self.identifier}{hint}"


class CommandError(KctlError):
    """Shell command execution errors."""

    def __init__(self, command: str, returncode: int, stderr: str = ""):
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"Command failed (exit {returncode}): {command}\n{stderr}".strip())


class APIError(KctlError):
    """HTTP API errors."""

    def __init__(self, status_code: int = 0, detail: str = ""):
        self.status_code = status_code
        self.detail = detail
        msg = f"API error ({status_code}): {detail}" if status_code else detail
        super().__init__(msg)


class ConnectionError(KctlError):  # noqa: A001
    """Cannot connect to remote service."""

    def __init__(self, url: str, cause: Exception | None = None):
        self.url = url
        self.cause = cause
        super().__init__(f"Cannot connect to {url}: {cause}")


class DockerError(KctlError):
    """Docker compose/exec execution errors."""

    def __init__(self, command: str, returncode: int, stderr: str = ""):
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"Command failed (exit {returncode}): {command}\n{stderr}".strip())


class ValidationError(KctlError):
    """Multi-error validation failures."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        msg = f"{len(errors)} validation error(s):\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(msg)
