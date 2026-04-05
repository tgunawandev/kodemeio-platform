"""Tests for kctl-api deploy commands."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from kctl_api.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# deploy --help checks
# ---------------------------------------------------------------------------
class TestDeployHelp:
    def test_deploy_help(self) -> None:
        result = runner.invoke(app, ["deploy", "--help"])
        assert result.exit_code == 0

    def test_deploy_status_help(self) -> None:
        result = runner.invoke(app, ["deploy", "status", "--help"])
        assert result.exit_code == 0

    def test_deploy_logs_help(self) -> None:
        result = runner.invoke(app, ["deploy", "logs", "--help"])
        assert result.exit_code == 0

    def test_deploy_restart_help(self) -> None:
        result = runner.invoke(app, ["deploy", "restart", "--help"])
        assert result.exit_code == 0

    def test_deploy_rollback_help(self) -> None:
        result = runner.invoke(app, ["deploy", "rollback", "--help"])
        assert result.exit_code == 0

    def test_deploy_list_help(self) -> None:
        result = runner.invoke(app, ["deploy", "list", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# deploy status (stub)
# ---------------------------------------------------------------------------
class TestDeployStatus:
    def test_status_no_app(self) -> None:
        result = runner.invoke(app, ["deploy", "status"])
        assert result.exit_code == 0

    def test_status_with_app_name(self) -> None:
        result = runner.invoke(app, ["deploy", "status", "api-main"])
        assert result.exit_code == 0
        assert "api-main" in result.output

    def test_status_all_apps(self) -> None:
        result = runner.invoke(app, ["deploy", "status"])
        assert result.exit_code == 0
        assert "all apps" in result.output.lower() or "not yet implemented" in result.output.lower()


# ---------------------------------------------------------------------------
# deploy logs (stub)
# ---------------------------------------------------------------------------
class TestDeployLogs:
    def test_logs_shows_app_name(self) -> None:
        result = runner.invoke(app, ["deploy", "logs", "api-main"])
        assert result.exit_code == 0
        assert "api-main" in result.output

    def test_logs_default_tail(self) -> None:
        result = runner.invoke(app, ["deploy", "logs", "api-main"])
        assert result.exit_code == 0
        assert "100" in result.output

    def test_logs_custom_tail(self) -> None:
        result = runner.invoke(app, ["deploy", "logs", "api-main", "--tail", "50"])
        assert result.exit_code == 0
        assert "50" in result.output

    def test_logs_not_implemented_message(self) -> None:
        result = runner.invoke(app, ["deploy", "logs", "api-main"])
        assert "not yet implemented" in result.output.lower()


# ---------------------------------------------------------------------------
# deploy restart (stub)
# ---------------------------------------------------------------------------
class TestDeployRestart:
    def test_restart_shows_app_name(self) -> None:
        result = runner.invoke(app, ["deploy", "restart", "api-main"])
        assert result.exit_code == 0
        assert "api-main" in result.output

    def test_restart_not_implemented(self) -> None:
        result = runner.invoke(app, ["deploy", "restart", "ai-main"])
        assert "not yet implemented" in result.output.lower()


# ---------------------------------------------------------------------------
# deploy rollback (stub)
# ---------------------------------------------------------------------------
class TestDeployRollback:
    def test_rollback_shows_app_name(self) -> None:
        result = runner.invoke(app, ["deploy", "rollback", "api-main"])
        assert result.exit_code == 0
        assert "api-main" in result.output

    def test_rollback_with_revision(self) -> None:
        result = runner.invoke(app, ["deploy", "rollback", "api-main", "--revision", "abc123"])
        assert result.exit_code == 0
        assert "abc123" in result.output

    def test_rollback_without_revision(self) -> None:
        result = runner.invoke(app, ["deploy", "rollback", "api-main"])
        assert result.exit_code == 0
        assert "previous revision" in result.output.lower()


# ---------------------------------------------------------------------------
# deploy list (stub)
# ---------------------------------------------------------------------------
class TestDeployList:
    def test_list_exit_ok(self) -> None:
        result = runner.invoke(app, ["deploy", "list"])
        assert result.exit_code == 0

    def test_list_not_implemented(self) -> None:
        result = runner.invoke(app, ["deploy", "list"])
        assert "not yet implemented" in result.output.lower()
