"""Tests for cycles commands."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_linear.cli import app

runner = CliRunner()


class TestCyclesSmoke:
    def test_cycles_help(self):
        result = runner.invoke(app, ["cycles", "--help"])
        assert result.exit_code == 0
        assert "current" in result.output
        assert "list" in result.output
        assert "show" in result.output
        assert "stats" in result.output

    def test_cycles_current_help(self):
        result = runner.invoke(app, ["cycles", "current", "--help"])
        assert result.exit_code == 0
        assert "--team" in result.output
