"""Smoke tests — CLI loads and help works."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_dbgate.cli import app


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "kctl-dbgate" in result.output.lower() or "DBGate" in result.output


def test_cli_version() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "kctl-dbgate" in result.output
