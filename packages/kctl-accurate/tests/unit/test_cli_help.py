"""--help renders cleanly for the root app."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_accurate.cli import app


def test_root_help_succeeds() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "kctl-accurate" in result.output


def test_root_help_lists_global_flags() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert "--profile" in result.output
    assert "--json" in result.output
    assert "--quiet" in result.output


def test_unknown_command_exits_nonzero() -> None:
    result = CliRunner().invoke(app, ["definitely-not-a-real-command"])
    assert result.exit_code != 0
