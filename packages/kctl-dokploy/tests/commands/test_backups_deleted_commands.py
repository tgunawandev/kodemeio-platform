"""Regression guard: these commands were deleted in the Dokploy-native redesign.

If someone re-introduces one of them, this test fails loudly so the
SSH+docker-exec code doesn't sneak back.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app


@pytest.mark.parametrize(
    "cmd",
    [
        ["backups", "dump-compose"],
        ["backups", "download"],
        ["backups", "restore-local"],
        ["backups", "refresh"],
        ["backups", "run-wait"],
    ],
)
def test_removed_command_rejected(cmd: list[str]) -> None:
    runner = CliRunner()
    result = runner.invoke(app, [*cmd, "--help"])
    # Typer returns non-zero and prints "No such command" when the command
    # is absent. We assert on exit code, not exact text, because Typer's
    # wording has varied across versions.
    assert result.exit_code != 0, (
        f"Command `{' '.join(cmd)}` still exists — it was supposed to be "
        f"deleted in the Dokploy-native redesign. See spec "
        f"kodemeio-docs/superpowers/specs/2026-04-19-kctl-dokploy-backup-"
        f"restore-redesign-design.md."
    )
