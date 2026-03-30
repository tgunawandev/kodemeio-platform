"""Smoke tests for kctl-op CLI."""

from typer.testing import CliRunner

from kctl_op.cli import app

runner = CliRunner()


class TestCLISmoke:
    def test_help_exits_zero(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0

    def test_version_output_contains_version(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert "0.1.0" in result.output
