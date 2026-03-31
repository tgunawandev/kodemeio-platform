"""Tests for groups commands."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_ak.cli import app

runner = CliRunner()


class TestGroupsHelp:
    def test_groups_list_help(self) -> None:
        result = runner.invoke(app, ["groups", "list", "--help"])
        assert result.exit_code == 0

    def test_groups_tree_help(self) -> None:
        result = runner.invoke(app, ["groups", "tree", "--help"])
        assert result.exit_code == 0

    def test_groups_create_help(self) -> None:
        result = runner.invoke(app, ["groups", "create", "--help"])
        assert result.exit_code == 0
        assert "--parent" in result.output

    def test_groups_sync_help(self) -> None:
        result = runner.invoke(app, ["groups", "sync", "--help"])
        assert result.exit_code == 0
        assert "--dry-run" in result.output

    def test_groups_add_user_help(self) -> None:
        result = runner.invoke(app, ["groups", "add-user", "--help"])
        assert result.exit_code == 0

    def test_groups_remove_user_help(self) -> None:
        result = runner.invoke(app, ["groups", "remove-user", "--help"])
        assert result.exit_code == 0

    def test_groups_members_help(self) -> None:
        result = runner.invoke(app, ["groups", "members", "--help"])
        assert result.exit_code == 0

    def test_groups_export_help(self) -> None:
        result = runner.invoke(app, ["groups", "export", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.output
