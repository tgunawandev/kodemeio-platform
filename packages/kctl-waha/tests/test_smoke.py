"""Smoke tests for kctl-waha CLI."""

from typer.testing import CliRunner

from kctl_waha.cli import app

runner = CliRunner()


class TestCLISmoke:
    def test_help_exits_zero(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0

    def test_version_contains_kctl_waha(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert "kctl-waha" in result.output
