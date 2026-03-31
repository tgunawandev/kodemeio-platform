"""Tests for system commands including convenience subcommands."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_ak.cli import app

runner = CliRunner()


class TestSystemSettings:
    def test_settings_help(self) -> None:
        result = runner.invoke(app, ["system", "settings", "--help"])
        assert result.exit_code == 0
        assert "settings" in result.output.lower()

    def test_update_setting_help(self) -> None:
        result = runner.invoke(app, ["system", "update-setting", "--help"])
        assert result.exit_code == 0
        assert "--key" in result.output
        assert "--value" in result.output


class TestSystemImpersonation:
    def test_help(self) -> None:
        result = runner.invoke(app, ["system", "impersonation", "--help"])
        assert result.exit_code == 0
        assert "impersonation" in result.output.lower()


class TestSystemUserChanges:
    def test_help(self) -> None:
        result = runner.invoke(app, ["system", "user-changes", "--help"])
        assert result.exit_code == 0
        assert "--name" in result.output
        assert "--email" in result.output
        assert "--username" in result.output


class TestSystemTokenDefaults:
    def test_help(self) -> None:
        result = runner.invoke(app, ["system", "token-defaults", "--help"])
        assert result.exit_code == 0
        assert "--duration" in result.output
        assert "--length" in result.output


class TestSystemEventRetention:
    def test_help(self) -> None:
        result = runner.invoke(app, ["system", "event-retention", "--help"])
        assert result.exit_code == 0


class TestSystemVersion:
    def test_help(self) -> None:
        result = runner.invoke(app, ["system", "version", "--help"])
        assert result.exit_code == 0

    def test_license_help(self) -> None:
        result = runner.invoke(app, ["system", "license", "--help"])
        assert result.exit_code == 0
