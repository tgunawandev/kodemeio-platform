"""Tests for kctl-waha messages commands."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_lib.exceptions import APIError
from kctl_waha.cli import app
from kctl_waha.core.client import BridgeClient, WahaClient


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock(spec=WahaClient)
    client.base_url = "https://waha.kodeme.io"
    return client


@pytest.fixture
def mock_bridge() -> MagicMock:
    bridge = MagicMock(spec=BridgeClient)
    bridge.base_url = "http://localhost:3000"
    return bridge


@contextmanager
def patched_clients(mock_client: MagicMock, mock_bridge: MagicMock):
    with patch("kctl_waha.core.callbacks.resolve_connection", return_value=("https://waha.test", "testkey")):
        with patch("kctl_waha.core.callbacks.resolve_bridge_url", return_value="http://bridge.test"):
            with patch("kctl_waha.core.callbacks.WahaClient", return_value=mock_client):
                with patch("kctl_waha.core.callbacks.BridgeClient", return_value=mock_bridge):
                    yield


def invoke(runner: CliRunner, args: list[str], mock_client: MagicMock, mock_bridge: MagicMock) -> object:
    with patched_clients(mock_client, mock_bridge):
        return runner.invoke(app, args)


class TestFormatPhone:
    """Verify _format_phone behaviour via the send command's chatId."""

    def test_strips_plus_prefix(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.post.return_value = {}
        invoke(runner, ["messages", "send", "+6281234567890", "Hi"], mock_client, mock_bridge)
        call_data = mock_client.post.call_args[1]["data"]
        assert call_data["chatId"] == "6281234567890@c.us"

    def test_appends_c_us(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.post.return_value = {}
        invoke(runner, ["messages", "send", "6281234567890", "Hello"], mock_client, mock_bridge)
        call_data = mock_client.post.call_args[1]["data"]
        assert call_data["chatId"] == "6281234567890@c.us"

    def test_does_not_double_append_c_us(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.post.return_value = {}
        invoke(runner, ["messages", "send", "6281234567890@c.us", "Hello"], mock_client, mock_bridge)
        call_data = mock_client.post.call_args[1]["data"]
        assert call_data["chatId"].count("@") == 1

    def test_strips_whitespace(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.post.return_value = {}
        invoke(runner, ["messages", "send", "  6281234  ", "Hi"], mock_client, mock_bridge)
        call_data = mock_client.post.call_args[1]["data"]
        assert call_data["chatId"] == "6281234@c.us"


class TestMessagesSend:
    def test_send_success(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.post.return_value = {"id": {"id": "msg-123"}}
        result = invoke(runner, ["messages", "send", "6281234567890", "Hello!"], mock_client, mock_bridge)
        assert result.exit_code == 0
        mock_client.post.assert_called_once_with(
            "sendText",
            data={
                "chatId": "6281234567890@c.us",
                "text": "Hello!",
                "session": "default",
            },
        )

    def test_send_custom_session(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = invoke(
            runner,
            ["messages", "send", "628111", "Hi", "--session", "my-session"],
            mock_client,
            mock_bridge,
        )
        assert result.exit_code == 0
        call_data = mock_client.post.call_args[1]["data"]
        assert call_data["session"] == "my-session"

    def test_send_api_error(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.post.side_effect = APIError(status_code=400, detail="Invalid phone")
        result = invoke(runner, ["messages", "send", "628111", "Hi"], mock_client, mock_bridge)
        assert result.exit_code == 1

    def test_send_response_with_string_id(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.post.return_value = {"id": "msg-abc"}
        result = invoke(runner, ["messages", "send", "628111", "Hi"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_send_empty_response(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = invoke(runner, ["messages", "send", "628111", "Hi"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_send_with_plus_phone(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.post.return_value = {}
        invoke(runner, ["messages", "send", "+6281234", "Hello"], mock_client, mock_bridge)
        call_data = mock_client.post.call_args[1]["data"]
        assert not call_data["chatId"].startswith("+")

    def test_send_dict_message_id_shown(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.post.return_value = {"id": {"id": "nested-id-xyz"}}
        result = invoke(runner, ["messages", "send", "628111", "Hello"], mock_client, mock_bridge)
        assert result.exit_code == 0


class TestMessagesSendImage:
    def test_send_image_success(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.post.return_value = {"id": {"id": "img-456"}}
        result = invoke(
            runner,
            ["messages", "send-image", "628111", "https://example.com/img.png"],
            mock_client,
            mock_bridge,
        )
        assert result.exit_code == 0
        mock_client.post.assert_called_once_with(
            "sendImage",
            data={
                "chatId": "628111@c.us",
                "file": {"url": "https://example.com/img.png"},
                "session": "default",
            },
        )

    def test_send_image_with_caption(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = invoke(
            runner,
            [
                "messages",
                "send-image",
                "628111",
                "https://example.com/img.png",
                "--caption",
                "Look at this!",
            ],
            mock_client,
            mock_bridge,
        )
        assert result.exit_code == 0
        call_data = mock_client.post.call_args[1]["data"]
        assert call_data["caption"] == "Look at this!"

    def test_send_image_without_caption_has_no_caption_key(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.post.return_value = {}
        invoke(
            runner,
            ["messages", "send-image", "628111", "https://example.com/img.png"],
            mock_client,
            mock_bridge,
        )
        call_data = mock_client.post.call_args[1]["data"]
        assert "caption" not in call_data

    def test_send_image_custom_session(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = invoke(
            runner,
            ["messages", "send-image", "628111", "https://example.com/img.png", "--session", "prod"],
            mock_client,
            mock_bridge,
        )
        assert result.exit_code == 0
        call_data = mock_client.post.call_args[1]["data"]
        assert call_data["session"] == "prod"

    def test_send_image_api_error(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.post.side_effect = APIError(status_code=422, detail="Invalid URL")
        result = invoke(
            runner,
            ["messages", "send-image", "628111", "https://example.com/img.png"],
            mock_client,
            mock_bridge,
        )
        assert result.exit_code == 1

    def test_send_image_with_string_msg_id(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.post.return_value = {"id": "flat-id"}
        result = invoke(
            runner,
            ["messages", "send-image", "628111", "https://example.com/x.jpg"],
            mock_client,
            mock_bridge,
        )
        assert result.exit_code == 0

    def test_send_image_file_url_in_body(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.post.return_value = {}
        invoke(
            runner,
            ["messages", "send-image", "628111", "https://cdn.example.com/photo.jpg"],
            mock_client,
            mock_bridge,
        )
        call_data = mock_client.post.call_args[1]["data"]
        assert call_data["file"] == {"url": "https://cdn.example.com/photo.jpg"}
