"""Exception hierarchy for kctl-op.

Re-exports base exceptions from kctl-common. Keeps VaultError, OpCliError,
and ConnectionError as service-specific to preserve client.py compatibility.
"""

from __future__ import annotations

from kctl_common.exceptions import (
    AuthenticationError as AuthenticationError,
)
from kctl_common.exceptions import (
    ConfigError as ConfigError,
)
from kctl_common.exceptions import (
    KctlError as KctlError,
)
from kctl_common.exceptions import (
    NotFoundError as NotFoundError,
)


class ConnectionError(KctlError):  # noqa: A001
    """Cannot connect to 1Password (op CLI not found or not working)."""

    def __init__(self, cause: Exception | None = None):
        self.cause = cause
        super().__init__(f"Cannot connect to 1Password: {cause}")


class VaultError(KctlError):
    """1Password vault operation error."""

    def __init__(self, vault: str, detail: str = ""):
        self.vault = vault
        self.detail = detail
        super().__init__(f"Vault error ({vault}): {detail}")


class OpCliError(KctlError):
    """1Password CLI (op) execution error."""

    def __init__(self, command: str, returncode: int, stderr: str = ""):
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"op CLI failed (exit {returncode}): {command}\n{stderr}".strip())
