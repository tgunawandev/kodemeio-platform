"""Rich output helpers for kctl-claude.

Re-exports kctl-common Output with backward-compatible aliases
for the method names used throughout kctl-claude commands.
"""

from __future__ import annotations

from typing import Any

from kctl_common.output import Output as _BaseOutput


class Output(_BaseOutput):
    """Output handler with kctl-claude backward-compatible aliases."""

    def ok(self, msg: str) -> None:
        """Alias for success()."""
        self.success(msg)

    def fail(self, msg: str) -> None:
        """Alias for error()."""
        self.error(msg)

    def dim(self, msg: str) -> None:
        """Print dimmed/informational text."""
        if not self.quiet:
            self.console.print(f"  [dim]{msg}[/dim]")

    def print(self, msg: str) -> None:  # type: ignore[override]
        """Alias for text()."""
        self.text(msg)

    def json_out(self, data: dict[str, Any] | list[Any]) -> None:
        """Alias for raw_json()."""
        self.raw_json(data)


__all__ = ["Output"]
