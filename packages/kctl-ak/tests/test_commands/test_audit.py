"""Tests for audit commands including suspicious."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_ak.cli import app

runner = CliRunner()


class TestAuditHelp:
    def test_audit_list_help(self) -> None:
        result = runner.invoke(app, ["audit", "list", "--help"])
        assert result.exit_code == 0
        assert "--action" in result.output

    def test_audit_logins_help(self) -> None:
        result = runner.invoke(app, ["audit", "logins", "--help"])
        assert result.exit_code == 0
        assert "--failed" in result.output

    def test_audit_changes_help(self) -> None:
        result = runner.invoke(app, ["audit", "changes", "--help"])
        assert result.exit_code == 0

    def test_audit_stats_help(self) -> None:
        result = runner.invoke(app, ["audit", "stats", "--help"])
        assert result.exit_code == 0
        assert "--days" in result.output

    def test_audit_export_help(self) -> None:
        result = runner.invoke(app, ["audit", "export", "--help"])
        assert result.exit_code == 0

    def test_audit_tail_help(self) -> None:
        result = runner.invoke(app, ["audit", "tail", "--help"])
        assert result.exit_code == 0

    def test_audit_suspicious_help(self) -> None:
        result = runner.invoke(app, ["audit", "suspicious", "--help"])
        assert result.exit_code == 0
        assert "--days" in result.output

    def test_audit_get_help(self) -> None:
        result = runner.invoke(app, ["audit", "get", "--help"])
        assert result.exit_code == 0
