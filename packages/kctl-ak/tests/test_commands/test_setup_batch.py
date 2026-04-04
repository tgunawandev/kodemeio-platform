"""Tests for setup batch command."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_ak.cli import app

runner = CliRunner()


class TestSetupBatchHelp:
    def test_batch_help(self) -> None:
        result = runner.invoke(app, ["setup", "batch", "--help"])
        assert result.exit_code == 0
        assert "--dry-run" in result.output
        assert "--output-env" in result.output

    def test_batch_has_file_option(self) -> None:
        result = runner.invoke(app, ["setup", "batch", "--help"])
        assert "--file" in result.output
