"""Test CLI entry point: --version, --help, no args, unknown command."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_zulip import __version__
from kctl_zulip.cli import app


def test_version(runner: CliRunner):
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help(runner: CliRunner):
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "kctl-zulip" in result.output.lower() or "zulip" in result.output.lower()


def test_no_args(runner: CliRunner):
    result = runner.invoke(app, [])
    # no_args_is_help=True causes Typer to show help with exit code 0 or 2
    assert result.exit_code in (0, 2)
    assert "Usage" in result.output or "usage" in result.output.lower()


def test_unknown_command(runner: CliRunner):
    result = runner.invoke(app, ["nonexistent-command-xyz"])
    assert result.exit_code != 0
