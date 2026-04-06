"""CLI smoke tests for kctl-opencloud."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_opencloud.cli import app


def test_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "OpenCloud" in result.output


def test_version() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "kctl-opencloud" in result.output


def test_health_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["health", "--help"])
    assert result.exit_code == 0


def test_users_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["users", "--help"])
    assert result.exit_code == 0


def test_groups_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["groups", "--help"])
    assert result.exit_code == 0


def test_spaces_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["spaces", "--help"])
    assert result.exit_code == 0


def test_shares_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["shares", "--help"])
    assert result.exit_code == 0


def test_config_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["config", "--help"])
    assert result.exit_code == 0


def test_doctor_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["doctor", "--help"])
    assert result.exit_code == 0


def test_dashboard_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["dashboard", "--help"])
    assert result.exit_code == 0
