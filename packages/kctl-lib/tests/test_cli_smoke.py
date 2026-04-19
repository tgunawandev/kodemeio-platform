"""Smoke test for the kctl-profiles meta-CLI."""

from __future__ import annotations

from typer.testing import CliRunner


def test_app_importable_and_help_works() -> None:
    from kctl_lib.cli.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "kctl-profiles" in result.output
