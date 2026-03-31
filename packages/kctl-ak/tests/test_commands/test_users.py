"""Tests for users commands including roles --verify."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_ak.cli import app

runner = CliRunner()


class TestUsersHelp:
    def test_users_list_help(self) -> None:
        result = runner.invoke(app, ["users", "list", "--help"])
        assert result.exit_code == 0
        assert "--active" in result.output

    def test_users_get_help(self) -> None:
        result = runner.invoke(app, ["users", "get", "--help"])
        assert result.exit_code == 0

    def test_users_create_help(self) -> None:
        result = runner.invoke(app, ["users", "create", "--help"])
        assert result.exit_code == 0
        assert "--groups" in result.output

    def test_users_search_help(self) -> None:
        result = runner.invoke(app, ["users", "search", "--help"])
        assert result.exit_code == 0

    def test_users_invite_help(self) -> None:
        result = runner.invoke(app, ["users", "invite", "--help"])
        assert result.exit_code == 0
        assert "--send-mail" in result.output

    def test_users_re_invite_help(self) -> None:
        result = runner.invoke(app, ["users", "re-invite", "--help"])
        assert result.exit_code == 0

    def test_users_pending_help(self) -> None:
        result = runner.invoke(app, ["users", "pending", "--help"])
        assert result.exit_code == 0

    def test_users_bulk_invite_help(self) -> None:
        result = runner.invoke(app, ["users", "bulk-invite", "--help"])
        assert result.exit_code == 0

    def test_users_export_help(self) -> None:
        result = runner.invoke(app, ["users", "export", "--help"])
        assert result.exit_code == 0

    def test_users_me_help(self) -> None:
        result = runner.invoke(app, ["users", "me", "--help"])
        assert result.exit_code == 0


class TestUsersRoles:
    def test_roles_help(self) -> None:
        result = runner.invoke(app, ["users", "roles", "--help"])
        assert result.exit_code == 0
        assert "--verify" in result.output

    def test_role_help(self) -> None:
        result = runner.invoke(app, ["users", "role", "--help"])
        assert result.exit_code == 0
        assert "--verify" in result.output

    def test_provision_help(self) -> None:
        result = runner.invoke(app, ["users", "provision", "--help"])
        assert result.exit_code == 0
        assert "--send-mail" in result.output
