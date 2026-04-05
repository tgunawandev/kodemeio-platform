"""Tests for group management commands."""

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


SAMPLE_GROUPS = [
    {"id": 1, "chat_id": "-1001234567890", "title": "General Chat", "type": "supergroup"},
    {"id": 2, "chat_id": "-1009876543210", "title": "Announcements", "type": "channel"},
]


class TestGroupsListCommand:
    def test_list_success(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"results": SAMPLE_GROUPS}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["groups", "list"])
        assert result.exit_code == 0
        mock_client.get.assert_called_once_with("groups")

    def test_list_empty(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"results": []}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["groups", "list"])
        assert result.exit_code == 0

    def test_list_raw_list_response(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_GROUPS
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["groups", "list"])
        assert result.exit_code == 0

    def test_list_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"results": SAMPLE_GROUPS}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["--json", "groups", "list"])
        assert result.exit_code == 0

    def test_list_single_group(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"results": [{"id": 1, "chat_id": "-100123", "title": "Solo", "type": "group"}]}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["groups", "list"])
        assert result.exit_code == 0


class TestGroupsGetCommand:
    def test_get_basic(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "id": 1,
            "chat_id": "-1001234567890",
            "title": "General Chat",
            "type": "supergroup",
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["groups", "get", "1"])
        assert result.exit_code == 0
        mock_client.get.assert_called_once_with("groups/1")

    def test_get_with_optional_fields(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "id": 1,
            "chat_id": "-1001234567890",
            "title": "Full Info Group",
            "type": "supergroup",
            "description": "A test group",
            "invite_link": "https://t.me/joinchat/abc123",
            "member_count": 42,
            "bot_id": 5,
            "bot": {"id": 5, "username": "mainbot"},
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-02-01T00:00:00Z",
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["groups", "get", "1"])
        assert result.exit_code == 0

    def test_get_with_bot_id_only(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "id": 2,
            "chat_id": "-100999",
            "title": "Bot Group",
            "type": "group",
            "bot_id": 3,
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["groups", "get", "2"])
        assert result.exit_code == 0

    def test_get_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "id": 3,
            "chat_id": "-100555",
            "title": "JSON Group",
            "type": "channel",
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["--json", "groups", "get", "3"])
        assert result.exit_code == 0


class TestGroupsUpdateCommand:
    def test_update_field(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.patch.return_value = {
            "id": 1,
            "chat_id": "-100123",
            "title": "New Title",
            "type": "supergroup",
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                ["groups", "update", "1", "--field", "title", "--value", "New Title"],
            )
        assert result.exit_code == 0
        mock_client.patch.assert_called_once_with("groups/1", json={"title": "New Title"})

    def test_update_description(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.patch.return_value = {
            "id": 2,
            "chat_id": "-100456",
            "title": "My Group",
            "type": "group",
            "description": "Updated description",
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                ["groups", "update", "2", "--field", "description", "--value", "Updated description"],
            )
        assert result.exit_code == 0
        mock_client.patch.assert_called_once_with("groups/2", json={"description": "Updated description"})

    def test_update_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.patch.return_value = {
            "id": 1,
            "chat_id": "-100123",
            "title": "New Title",
            "type": "supergroup",
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                ["--json", "groups", "update", "1", "--field", "title", "--value", "New Title"],
            )
        assert result.exit_code == 0
