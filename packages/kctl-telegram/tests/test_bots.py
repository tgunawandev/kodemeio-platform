"""Tests for bot management commands."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_telegram.cli import app
from kctl_telegram.core.callbacks import AppContext
from kctl_telegram.core.client import TelegramClient


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock(spec=TelegramClient)
    client.base_url = "https://telegram.kodeme.io"
    return client


class TestBotsListCommand:
    def test_list_success(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "results": [
                {"id": 1, "username": "testbot", "display_name": "Test Bot", "is_active": True},
                {"id": 2, "username": "bot2", "display_name": "Bot Two", "is_active": False},
            ]
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["bots", "list"])
        assert result.exit_code == 0
        mock_client.get.assert_called_once_with("bots")

    def test_list_empty(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"results": []}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["bots", "list"])
        assert result.exit_code == 0

    def test_list_raw_list_response(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """Handles a raw list response (not wrapped in 'results')."""
        mock_client.get.return_value = [
            {"id": 1, "username": "testbot", "display_name": "Test Bot", "is_active": True},
        ]
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["bots", "list"])
        assert result.exit_code == 0

    def test_list_shows_active_status(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "results": [{"id": 1, "username": "active_bot", "display_name": "Active", "is_active": True}]
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["bots", "list"])
        assert result.exit_code == 0

    def test_list_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "results": [{"id": 1, "username": "testbot", "display_name": "Test Bot", "is_active": True}]
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["--json", "bots", "list"])
        assert result.exit_code == 0


class TestBotsGetCommand:
    def test_get_success(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "id": 1,
            "username": "testbot",
            "display_name": "Test Bot",
            "is_active": True,
            "token": "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ12345678",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["bots", "get", "1"])
        assert result.exit_code == 0
        mock_client.get.assert_called_once_with("bots/1")

    def test_get_without_token(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "id": 2,
            "username": "bot2",
            "display_name": "Bot Two",
            "is_active": False,
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["bots", "get", "2"])
        assert result.exit_code == 0

    def test_get_short_token_masked(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """Short tokens (<=10 chars) get masked as ****."""
        mock_client.get.return_value = {
            "id": 3,
            "username": "bot3",
            "display_name": "Bot Three",
            "is_active": True,
            "token": "short",
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["bots", "get", "3"])
        assert result.exit_code == 0

    def test_get_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "id": 1,
            "username": "testbot",
            "display_name": "Test Bot",
            "is_active": True,
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["--json", "bots", "get", "1"])
        assert result.exit_code == 0


class TestBotsAddCommand:
    def test_add_success(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {
            "id": 10,
            "username": "newbot",
            "display_name": "New Bot",
            "is_active": True,
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["bots", "add", "--token", "fake:token123"])
        assert result.exit_code == 0
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == "bots"

    def test_add_with_display_name(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {
            "id": 11,
            "username": "namedbot",
            "display_name": "Named Bot",
            "is_active": True,
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                ["bots", "add", "--token", "fake:token456", "--display-name", "Named Bot"],
            )
        assert result.exit_code == 0
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"]["display_name"] == "Named Bot"

    def test_add_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {
            "id": 12,
            "username": "jsonbot",
            "display_name": "JSON Bot",
            "is_active": True,
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["--json", "bots", "add", "--token", "fake:json789"])
        assert result.exit_code == 0


class TestBotsUpdateCommand:
    def test_update_display_name(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.patch.return_value = {
            "id": 1,
            "username": "testbot",
            "display_name": "Updated Name",
            "is_active": True,
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["bots", "update", "1", "--display-name", "Updated Name"])
        assert result.exit_code == 0
        mock_client.patch.assert_called_once_with("bots/1", json={"display_name": "Updated Name"})

    def test_update_active_flag(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.patch.return_value = {
            "id": 1,
            "username": "testbot",
            "display_name": "Test Bot",
            "is_active": False,
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["bots", "update", "1", "--no-active"])
        assert result.exit_code == 0
        call_kwargs = mock_client.patch.call_args
        assert call_kwargs[1]["json"]["is_active"] is False

    def test_update_no_changes_exits_1(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["bots", "update", "1"])
        assert result.exit_code == 1
        mock_client.patch.assert_not_called()

    def test_update_both_fields(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.patch.return_value = {
            "id": 1,
            "username": "testbot",
            "display_name": "New Name",
            "is_active": True,
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                ["bots", "update", "1", "--display-name", "New Name", "--is-active"],
            )
        assert result.exit_code == 0
        call_kwargs = mock_client.patch.call_args
        assert call_kwargs[1]["json"]["display_name"] == "New Name"
        assert call_kwargs[1]["json"]["is_active"] is True


class TestBotsRemoveCommand:
    def test_remove_with_force(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["bots", "remove", "1", "--force"])
        assert result.exit_code == 0
        mock_client.delete.assert_called_once_with("bots/1")

    def test_remove_without_force_confirms(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"id": 1, "display_name": "Test Bot", "username": "testbot"}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["bots", "remove", "1"], input="y\n")
        assert result.exit_code == 0
        mock_client.delete.assert_called_once_with("bots/1")

    def test_remove_cancel_confirmation(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"id": 1, "display_name": "Test Bot", "username": "testbot"}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["bots", "remove", "1"], input="n\n")
        assert result.exit_code == 0
        mock_client.delete.assert_not_called()

    def test_remove_force_skips_get(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """With --force, no GET request is made to fetch bot name."""
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["bots", "remove", "5", "--force"])
        assert result.exit_code == 0
        mock_client.get.assert_not_called()
        mock_client.delete.assert_called_once_with("bots/5")
