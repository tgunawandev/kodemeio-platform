"""Smoke tests for projects, teams, labels, users, and dashboard commands."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_linear.cli import app

runner = CliRunner()


class TestProjectsSmoke:
    def test_help(self):
        result = runner.invoke(app, ["projects", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "show" in result.output


class TestTeamsSmoke:
    def test_help(self):
        result = runner.invoke(app, ["teams", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "show" in result.output


class TestLabelsSmoke:
    def test_help(self):
        result = runner.invoke(app, ["labels", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "create" in result.output


class TestUsersSmoke:
    def test_help(self):
        result = runner.invoke(app, ["users", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "me" in result.output


class TestDashboardSmoke:
    def test_help(self):
        result = runner.invoke(app, ["dashboard", "--help"])
        assert result.exit_code == 0
