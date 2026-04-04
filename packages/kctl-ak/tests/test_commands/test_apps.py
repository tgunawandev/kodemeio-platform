"""Tests for apps commands including audit/orphaned."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_ak.cli import app

runner = CliRunner()


class TestAppsHelp:
    def test_apps_list_help(self) -> None:
        result = runner.invoke(app, ["apps", "list", "--help"])
        assert result.exit_code == 0

    def test_apps_get_help(self) -> None:
        result = runner.invoke(app, ["apps", "get", "--help"])
        assert result.exit_code == 0

    def test_apps_create_help(self) -> None:
        result = runner.invoke(app, ["apps", "create", "--help"])
        assert result.exit_code == 0
        assert "--provider" in result.output

    def test_apps_launch_urls_help(self) -> None:
        result = runner.invoke(app, ["apps", "launch-urls", "--help"])
        assert result.exit_code == 0

    def test_apps_access_help(self) -> None:
        result = runner.invoke(app, ["apps", "access", "--help"])
        assert result.exit_code == 0


class TestAppsAudit:
    def test_audit_help(self) -> None:
        result = runner.invoke(app, ["apps", "audit", "--help"])
        assert result.exit_code == 0
        assert "missing" in result.output.lower() or "provider" in result.output.lower()


class TestAppsOrphaned:
    def test_orphaned_help(self) -> None:
        result = runner.invoke(app, ["apps", "orphaned", "--help"])
        assert result.exit_code == 0
        assert "no" in result.output.lower() or "provider" in result.output.lower()


class TestAppsSetIcon:
    def test_set_icon_help(self) -> None:
        result = runner.invoke(app, ["apps", "set-icon", "--help"])
        assert result.exit_code == 0
        assert "slug" in result.output.lower()
        assert "source" in result.output.lower()
