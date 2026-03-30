"""Tests for users command group."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_notion.cli import app

runner = CliRunner()


class TestUsersList:
    def test_list_users(self, httpx_mock, mock_users_list):
        httpx_mock.add_response(json=mock_users_list)
        result = runner.invoke(app, ["users", "list"])
        assert result.exit_code == 0
        assert "Alice Smith" in result.output
        assert "Test Bot" in result.output

    def test_list_users_json(self, httpx_mock, mock_users_list):
        httpx_mock.add_response(json=mock_users_list)
        result = runner.invoke(app, ["--json", "users", "list"])
        assert result.exit_code == 0
        assert "users" in result.output

    def test_list_users_empty(self, httpx_mock):
        httpx_mock.add_response(json={"object": "list", "results": [], "has_more": False})
        result = runner.invoke(app, ["users", "list"])
        assert result.exit_code == 0
        assert "no users" in result.output.lower()


class TestUsersMe:
    def test_me(self, httpx_mock, mock_notion_me):
        httpx_mock.add_response(json=mock_notion_me)
        result = runner.invoke(app, ["users", "me"])
        assert result.exit_code == 0
        assert "Test Integration" in result.output

    def test_me_json(self, httpx_mock, mock_notion_me):
        httpx_mock.add_response(json=mock_notion_me)
        result = runner.invoke(app, ["--json", "users", "me"])
        assert result.exit_code == 0
        assert "Test Integration" in result.output
