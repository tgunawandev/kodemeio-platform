"""Tests for health command."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_linear.cli import app

runner = CliRunner()


class TestHealthCommand:
    def test_health_help(self):
        """Health command --help works."""
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0
        assert "health" in result.output.lower()
