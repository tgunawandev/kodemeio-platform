"""Regression guard: which backup workflow commands exist (or are gone).

History: the Dokploy-native redesign deleted SSH+docker-exec commands
(``dump-compose``, ``restore-local``, ``refresh``). Those remain deleted.

2026-04-19: ``download``, ``run-wait``, and ``pull`` were *re-introduced*
as thin boto3-backed helpers (no SSH), because the native
``backup.restoreBackupWithLogs`` stream only covers Dokploy-managed
targets — devs pulling a prod dump onto a local/raw postgres still need
a way to download and restore.

If someone re-introduces one of the still-deleted commands, this test
fails loudly so the old SSH+docker-exec code doesn't sneak back.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app


@pytest.mark.parametrize(
    "cmd",
    [
        ["backups", "dump-compose"],
        ["backups", "restore-local"],
        ["backups", "refresh"],
    ],
)
def test_removed_command_rejected(cmd: list[str]) -> None:
    runner = CliRunner()
    result = runner.invoke(app, [*cmd, "--help"])
    assert result.exit_code != 0, (
        f"Command `{' '.join(cmd)}` still exists — it was supposed to be deleted in the Dokploy-native redesign."
    )


@pytest.mark.parametrize(
    "cmd",
    [
        ["backups", "pull"],
        ["backups", "download"],
        ["backups", "run-wait"],
    ],
)
def test_reintroduced_command_present(cmd: list[str]) -> None:
    """These were re-added 2026-04-19 for the dev-loop pull-to-local workflow."""
    runner = CliRunner()
    result = runner.invoke(app, [*cmd, "--help"])
    assert result.exit_code == 0, f"Command `{' '.join(cmd)}` should exist but --help returned non-zero."
