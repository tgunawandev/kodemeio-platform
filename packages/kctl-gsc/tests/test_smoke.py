"""Smoke tests — verify CLI boots."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_gsc import __version__
from kctl_gsc.cli import app


def test_help_shows_groups() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for group in (
        "properties",
        "queries",
        "pages",
        "sitemaps",
        "inspect",
        "reports",
        "export",
        "config",
        "doctor",
    ):
        assert group in result.stdout


def test_version_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
