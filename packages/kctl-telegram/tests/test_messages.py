"""Tests for message send/broadcast/schedule commands."""

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


class TestMessagesSendCommand:
    def test_send_basic(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"message_id": 42, "ok": True}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                ["messages", "send", "--chat-id", "-100123", "--text", "Hello World"],
            )
        assert result.exit_code == 0
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == "messages/send"
        assert call_kwargs[1]["json"]["chat_id"] == "-100123"
        assert call_kwargs[1]["json"]["text"] == "Hello World"

    def test_send_with_bot_id(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"message_id": 99, "ok": True}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                ["messages", "send", "--chat-id", "-100456", "--text", "Hi", "--bot-id", "3"],
            )
        assert result.exit_code == 0
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"]["bot_id"] == 3

    def test_send_with_parse_mode(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"message_id": 55, "ok": True}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "messages",
                    "send",
                    "--chat-id",
                    "-100789",
                    "--text",
                    "<b>Bold</b>",
                    "--parse-mode",
                    "HTML",
                ],
            )
        assert result.exit_code == 0
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"]["parse_mode"] == "HTML"

    def test_send_no_message_id_in_response(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """Handles response without message_id field."""
        mock_client.post.return_value = {"ok": True}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                ["messages", "send", "--chat-id", "-100123", "--text", "Test"],
            )
        assert result.exit_code == 0

    def test_send_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"message_id": 42, "ok": True}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                ["--json", "messages", "send", "--chat-id", "-100123", "--text", "Hello"],
            )
        assert result.exit_code == 0


class TestMessagesBroadcastCommand:
    def test_broadcast_basic(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"sent_count": 5, "ok": True}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                ["messages", "broadcast", "--text", "Broadcast message"],
            )
        assert result.exit_code == 0
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == "messages/broadcast"
        assert call_kwargs[1]["json"]["text"] == "Broadcast message"

    def test_broadcast_with_bot_id(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"sent_count": 3}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                ["messages", "broadcast", "--text", "Hello", "--bot-id", "2"],
            )
        assert result.exit_code == 0
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"]["bot_id"] == 2

    def test_broadcast_uses_count_field_fallback(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """Uses 'count' key if 'sent_count' is not in response."""
        mock_client.post.return_value = {"count": 7}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                ["messages", "broadcast", "--text", "Fallback count test"],
            )
        assert result.exit_code == 0

    def test_broadcast_with_parse_mode(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"sent_count": 2}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                ["messages", "broadcast", "--text", "*bold*", "--parse-mode", "Markdown"],
            )
        assert result.exit_code == 0
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"]["parse_mode"] == "Markdown"

    def test_broadcast_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"sent_count": 1}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                ["--json", "messages", "broadcast", "--text", "JSON broadcast"],
            )
        assert result.exit_code == 0


class TestMessagesScheduleCommand:
    def test_schedule_basic(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"id": 101, "status": "scheduled"}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "messages",
                    "schedule",
                    "--text",
                    "Scheduled msg",
                    "--target-id",
                    "-100123",
                    "--at",
                    "2026-05-01T10:00:00Z",
                ],
            )
        assert result.exit_code == 0
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == "messages/schedule"
        assert call_kwargs[1]["json"]["scheduled_at"] == "2026-05-01T10:00:00Z"
        assert call_kwargs[1]["json"]["target_id"] == "-100123"

    def test_schedule_with_bot_id(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"id": 102, "status": "scheduled"}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "messages",
                    "schedule",
                    "--text",
                    "Bot scheduled",
                    "--target-id",
                    "-100456",
                    "--at",
                    "2026-06-01T09:00:00Z",
                    "--bot-id",
                    "5",
                ],
            )
        assert result.exit_code == 0
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"]["bot_id"] == 5

    def test_schedule_no_id_in_response(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"status": "scheduled"}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "messages",
                    "schedule",
                    "--text",
                    "No ID",
                    "--target-id",
                    "-100789",
                    "--at",
                    "2026-07-01T08:00:00Z",
                ],
            )
        assert result.exit_code == 0

    def test_schedule_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"id": 200, "status": "scheduled"}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json",
                    "messages",
                    "schedule",
                    "--text",
                    "JSON schedule",
                    "--target-id",
                    "-100111",
                    "--at",
                    "2026-08-01T07:00:00Z",
                ],
            )
        assert result.exit_code == 0


class TestMessagesScheduledCommand:
    def test_scheduled_list(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "results": [
                {
                    "id": 1,
                    "target_id": "-100123",
                    "text": "Hello at 10am",
                    "scheduled_at": "2026-05-01T10:00:00Z",
                    "status": "pending",
                },
                {
                    "id": 2,
                    "chat_id": "-100456",
                    "text": "Long text " + "x" * 60,
                    "scheduled_at": "2026-05-02T12:00:00Z",
                    "status": "sent",
                },
            ]
        }
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["messages", "scheduled"])
        assert result.exit_code == 0
        mock_client.get.assert_called_once_with("messages/scheduled")

    def test_scheduled_empty(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"results": []}
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["messages", "scheduled"])
        assert result.exit_code == 0

    def test_scheduled_raw_list(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {
                "id": 3,
                "target_id": "-100789",
                "text": "Direct list",
                "scheduled_at": "2026-05-03T08:00:00Z",
                "status": "pending",
            }
        ]
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["messages", "scheduled"])
        assert result.exit_code == 0


class TestMessagesCancelCommand:
    def test_cancel_success(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["messages", "cancel", "101"])
        assert result.exit_code == 0
        mock_client.delete.assert_called_once_with("messages/scheduled/101")

    def test_cancel_different_id(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["messages", "cancel", "999"])
        assert result.exit_code == 0
        mock_client.delete.assert_called_once_with("messages/scheduled/999")
