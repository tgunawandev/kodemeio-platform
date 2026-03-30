"""Tests for issues commands."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_linear.cli import app

runner = CliRunner()


class TestIssuesSmoke:
    def test_issues_help(self):
        result = runner.invoke(app, ["issues", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "show" in result.output
        assert "create" in result.output
        assert "update" in result.output
        assert "comment" in result.output
        assert "search" in result.output

    def test_issues_list_help(self):
        result = runner.invoke(app, ["issues", "list", "--help"])
        assert result.exit_code == 0
        assert "--team" in result.output
        assert "--state" in result.output
        assert "--assignee" in result.output

    def test_issues_create_help(self):
        result = runner.invoke(app, ["issues", "create", "--help"])
        assert result.exit_code == 0
        assert "--title" in result.output
        assert "--priority" in result.output
