"""Smoke test: --version produces a version string and exits 0."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_accurate import __version__
from kctl_accurate.cli import app


def test_version_flag_prints_version() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert __version__ in result.output


def test_version_string_is_present() -> None:
    assert isinstance(__version__, str)
    assert __version__  # not empty
