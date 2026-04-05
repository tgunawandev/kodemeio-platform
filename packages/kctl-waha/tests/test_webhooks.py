"""Tests for kctl-waha webhooks commands."""

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


class TestWebhooksList:
    def test_list_no_sessions(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = []
        result = invoke(runner, ["webhooks", "list"], mock_client, mock_bridge)
        assert result.exit_code == 0
        mock_client.get.assert_called_once_with("sessions/", params={"all": "true"})

    def test_list_session_no_webhooks(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = [
            {"name": "default", "status": "WORKING", "config": {"webhooks": []}},
        ]
        result = invoke(runner, ["webhooks", "list"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_list_session_with_webhook(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = [
            {
                "name": "default",
                "status": "WORKING",
                "config": {"webhooks": [{"url": "https://hook.example.com", "events": ["message", "session.status"]}]},
            }
        ]
        result = invoke(runner, ["webhooks", "list"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_list_session_webhook_with_hmac(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.get.return_value = [
            {
                "name": "s1",
                "status": "WORKING",
                "config": {
                    "webhooks": [
                        {
                            "url": "https://secure.example.com/hook",
                            "events": ["message"],
                            "hmac": {"key": "secret"},
                        }
                    ]
                },
            }
        ]
        result = invoke(runner, ["webhooks", "list"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_list_session_webhook_empty_events(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.get.return_value = [
            {
                "name": "s1",
                "status": "WORKING",
                "config": {"webhooks": [{"url": "https://example.com", "events": []}]},
            }
        ]
        result = invoke(runner, ["webhooks", "list"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_list_session_no_config_key(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.get.return_value = [
            {"name": "old", "status": "STOPPED"},
        ]
        result = invoke(runner, ["webhooks", "list"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_list_multiple_sessions_mixed(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.get.return_value = [
            {"name": "a", "config": {"webhooks": [{"url": "https://a.com", "events": ["message"]}]}},
            {"name": "b", "config": {"webhooks": []}},
            {"name": "c", "config": {}},
        ]
        result = invoke(runner, ["webhooks", "list"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_list_api_error(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.side_effect = APIError(status_code=500, detail="Server error")
        result = invoke(runner, ["webhooks", "list"], mock_client, mock_bridge)
        assert result.exit_code == 1

    def test_list_non_list_response(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = {"error": "unexpected"}
        result = invoke(runner, ["webhooks", "list"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_list_session_no_hmac_shows_no(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.get.return_value = [
            {
                "name": "s1",
                "config": {"webhooks": [{"url": "https://example.com"}]},
            }
        ]
        result = invoke(runner, ["webhooks", "list"], mock_client, mock_bridge)
        assert result.exit_code == 0


class TestWebhooksSet:
    def test_set_url_only(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.put.return_value = {}
        result = invoke(
            runner,
            ["webhooks", "set", "default", "--url", "https://hook.example.com"],
            mock_client,
            mock_bridge,
        )
        assert result.exit_code == 0
        mock_client.put.assert_called_once_with(
            "sessions/default",
            data={"config": {"webhooks": [{"url": "https://hook.example.com"}]}},
        )

    def test_set_with_events(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.put.return_value = {}
        result = invoke(
            runner,
            [
                "webhooks",
                "set",
                "default",
                "--url",
                "https://hook.example.com",
                "--events",
                "message,session.status",
            ],
            mock_client,
            mock_bridge,
        )
        assert result.exit_code == 0
        call_data = mock_client.put.call_args[1]["data"]
        wh = call_data["config"]["webhooks"][0]
        assert wh["events"] == ["message", "session.status"]

    def test_set_events_stripped(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.put.return_value = {}
        invoke(
            runner,
            [
                "webhooks",
                "set",
                "s1",
                "--url",
                "https://h.com",
                "--events",
                " message , session.status ",
            ],
            mock_client,
            mock_bridge,
        )
        call_data = mock_client.put.call_args[1]["data"]
        wh = call_data["config"]["webhooks"][0]
        assert "message" in wh["events"]
        assert "session.status" in wh["events"]

    def test_set_with_hmac_key(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.put.return_value = {}
        result = invoke(
            runner,
            [
                "webhooks",
                "set",
                "default",
                "--url",
                "https://hook.example.com",
                "--hmac-key",
                "my-secret",
            ],
            mock_client,
            mock_bridge,
        )
        assert result.exit_code == 0
        call_data = mock_client.put.call_args[1]["data"]
        wh = call_data["config"]["webhooks"][0]
        assert wh["hmac"] == {"key": "my-secret"}

    def test_set_no_hmac_key_means_no_hmac_in_body(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.put.return_value = {}
        invoke(
            runner,
            ["webhooks", "set", "s1", "--url", "https://hook.example.com"],
            mock_client,
            mock_bridge,
        )
        call_data = mock_client.put.call_args[1]["data"]
        wh = call_data["config"]["webhooks"][0]
        assert "hmac" not in wh

    def test_set_api_error(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.put.side_effect = APIError(status_code=400, detail="Bad request")
        result = invoke(
            runner,
            ["webhooks", "set", "default", "--url", "https://hook.example.com"],
            mock_client,
            mock_bridge,
        )
        assert result.exit_code == 1

    def test_set_with_all_options(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.put.return_value = {}
        result = invoke(
            runner,
            [
                "webhooks",
                "set",
                "prod",
                "--url",
                "https://n8n.example.com/waha",
                "--events",
                "message,message.ack",
                "--hmac-key",
                "supersecret",
            ],
            mock_client,
            mock_bridge,
        )
        assert result.exit_code == 0
        call_data = mock_client.put.call_args[1]["data"]
        wh = call_data["config"]["webhooks"][0]
        assert wh["url"] == "https://n8n.example.com/waha"
        assert wh["events"] == ["message", "message.ack"]
        assert wh["hmac"] == {"key": "supersecret"}

    def test_set_success_message(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.put.return_value = {}
        result = invoke(
            runner,
            ["webhooks", "set", "mysession", "--url", "https://hook.example.com"],
            mock_client,
            mock_bridge,
        )
        assert result.exit_code == 0
        assert "mysession" in result.output
