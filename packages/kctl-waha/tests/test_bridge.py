"""Tests for kctl-waha bridge commands."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from kctl_lib.exceptions import APIError, ConnectionError as KctlConnectionError
from kctl_lib.output import Output
from kctl_waha.cli import app
from kctl_waha.core.callbacks import AppContext
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


@pytest.fixture
def mock_context(mock_client: MagicMock, mock_bridge: MagicMock) -> AppContext:
    ctx = AppContext(quiet=True)
    ctx._client = mock_client
    ctx._bridge = mock_bridge
    ctx._output = Output(json_mode=False, quiet=True, format="pretty")
    return ctx


def invoke(runner: CliRunner, args: list[str], ctx: AppContext) -> object:
    return runner.invoke(app, args, obj=ctx)


class TestBridgeHealth:
    def test_health_ok(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.check_health.return_value = {"status": "ok"}
        result = invoke(runner, ["bridge", "health"], mock_context)
        assert result.exit_code == 0
        mock_context.bridge.check_health.assert_called_once()

    def test_health_empty_response_fails(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.check_health.return_value = {}
        result = invoke(runner, ["bridge", "health"], mock_context)
        assert result.exit_code == 1

    def test_health_none_response_fails(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.check_health.return_value = None
        result = invoke(runner, ["bridge", "health"], mock_context)
        assert result.exit_code == 1

    def test_health_exception_fails(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.check_health.side_effect = KctlConnectionError(
            "http://localhost:3000", Exception("refused")
        )
        result = invoke(runner, ["bridge", "health"], mock_context)
        assert result.exit_code == 1

    def test_health_extra_fields_displayed(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.check_health.return_value = {
            "status": "ok",
            "uptime_seconds": 3600,
            "version": "1.2.3",
        }
        result = invoke(runner, ["bridge", "health"], mock_context)
        assert result.exit_code == 0

    def test_health_api_error(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.check_health.side_effect = APIError(status_code=503, detail="Unavailable")
        result = invoke(runner, ["bridge", "health"], mock_context)
        assert result.exit_code == 1


class TestBridgeStatus:
    def test_status_full_config(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.get.return_value = {
            "waha": {"url": "https://waha.kodeme.io", "api_key": "secret123"},
            "chatwoot": {"url": "https://chat.example.com", "token": "tok123"},
            "odoo": {"url": "https://odoo.example.com", "password": "pass"},
        }
        result = invoke(runner, ["bridge", "status"], mock_context)
        assert result.exit_code == 0
        mock_context.bridge.get.assert_called_once_with("setup/status")

    def test_status_masks_secrets(self, runner: CliRunner, mock_context: AppContext) -> None:
        """Secrets (api_key, token, password) should not appear in plain text."""
        mock_context.bridge.get.return_value = {
            "waha": {"url": "https://waha.kodeme.io", "api_key": "supersecret"},
        }
        result = invoke(runner, ["bridge", "status"], mock_context)
        assert result.exit_code == 0
        # Secret value should not appear in output
        assert "supersecret" not in result.output

    def test_status_empty_response_shows_fallback(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.get.return_value = {}
        result = invoke(runner, ["bridge", "status"], mock_context)
        assert result.exit_code == 0

    def test_status_non_dict_response_fails(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.get.return_value = ["unexpected", "list"]
        result = invoke(runner, ["bridge", "status"], mock_context)
        assert result.exit_code == 1

    def test_status_api_error(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.get.side_effect = APIError(status_code=500, detail="Server error")
        result = invoke(runner, ["bridge", "status"], mock_context)
        assert result.exit_code == 1

    def test_status_connection_error(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.get.side_effect = KctlConnectionError("http://localhost:3000", Exception("refused"))
        result = invoke(runner, ["bridge", "status"], mock_context)
        assert result.exit_code == 1

    def test_status_only_waha_section(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.get.return_value = {
            "waha": {"url": "https://waha.kodeme.io"},
        }
        result = invoke(runner, ["bridge", "status"], mock_context)
        assert result.exit_code == 0

    def test_status_empty_sections_skipped(self, runner: CliRunner, mock_context: AppContext) -> None:
        """Empty dicts for waha/chatwoot/odoo should not produce sections."""
        mock_context.bridge.get.return_value = {
            "waha": {},
            "chatwoot": {},
            "odoo": {},
        }
        result = invoke(runner, ["bridge", "status"], mock_context)
        assert result.exit_code == 0


class TestBridgeSetupChatwoot:
    def test_setup_no_options(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.post.return_value = {"inbox_id": 42, "status": "created"}
        result = invoke(runner, ["bridge", "setup-chatwoot"], mock_context)
        assert result.exit_code == 0
        mock_context.bridge.post.assert_called_once_with("setup/chatwoot-inbox", data={})

    def test_setup_with_name(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.post.return_value = {}
        result = invoke(runner, ["bridge", "setup-chatwoot", "--name", "My Inbox"], mock_context)
        assert result.exit_code == 0
        call_data = mock_context.bridge.post.call_args[1]["data"]
        assert call_data["name"] == "My Inbox"

    def test_setup_with_callback_url(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.post.return_value = {}
        result = invoke(
            runner,
            ["bridge", "setup-chatwoot", "--callback-url", "https://chat.example.com/wh"],
            mock_context,
        )
        assert result.exit_code == 0
        call_data = mock_context.bridge.post.call_args[1]["data"]
        assert call_data["callback_url"] == "https://chat.example.com/wh"

    def test_setup_with_all_options(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.post.return_value = {"inbox_id": 7}
        result = invoke(
            runner,
            [
                "bridge",
                "setup-chatwoot",
                "--name",
                "WhatsApp Inbox",
                "--callback-url",
                "https://chat.example.com/wh",
            ],
            mock_context,
        )
        assert result.exit_code == 0
        call_data = mock_context.bridge.post.call_args[1]["data"]
        assert call_data["name"] == "WhatsApp Inbox"
        assert call_data["callback_url"] == "https://chat.example.com/wh"

    def test_setup_api_error(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.post.side_effect = APIError(status_code=422, detail="Invalid config")
        result = invoke(runner, ["bridge", "setup-chatwoot"], mock_context)
        assert result.exit_code == 1

    def test_setup_json_mode(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context._output = Output(json_mode=True, quiet=True, format="json")
        mock_context.bridge.post.return_value = {"inbox_id": 5}
        result = invoke(runner, ["bridge", "setup-chatwoot"], mock_context)
        assert result.exit_code == 0

    def test_setup_displays_result_fields(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.post.return_value = {"inbox_id": 42, "inbox_name": "WA", "status": "ok"}
        result = invoke(runner, ["bridge", "setup-chatwoot"], mock_context)
        assert result.exit_code == 0


class TestBridgeSetupWebhook:
    def test_setup_webhook_default_session(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.post.return_value = {"configured": True}
        result = invoke(runner, ["bridge", "setup-webhook"], mock_context)
        assert result.exit_code == 0
        call_data = mock_context.bridge.post.call_args[1]["data"]
        assert call_data["session"] == "default"

    def test_setup_webhook_custom_session(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.post.return_value = {}
        result = invoke(runner, ["bridge", "setup-webhook", "--session", "prod"], mock_context)
        assert result.exit_code == 0
        call_data = mock_context.bridge.post.call_args[1]["data"]
        assert call_data["session"] == "prod"

    def test_setup_webhook_with_url(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.post.return_value = {}
        result = invoke(
            runner,
            ["bridge", "setup-webhook", "--webhook-url", "https://bridge.example.com/hook"],
            mock_context,
        )
        assert result.exit_code == 0
        call_data = mock_context.bridge.post.call_args[1]["data"]
        assert call_data["webhook_url"] == "https://bridge.example.com/hook"

    def test_setup_webhook_no_url_no_key(self, runner: CliRunner, mock_context: AppContext) -> None:
        """Without --webhook-url, the key should not be in the body."""
        mock_context.bridge.post.return_value = {}
        invoke(runner, ["bridge", "setup-webhook"], mock_context)
        call_data = mock_context.bridge.post.call_args[1]["data"]
        assert "webhook_url" not in call_data

    def test_setup_webhook_posts_to_correct_endpoint(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.post.return_value = {}
        invoke(runner, ["bridge", "setup-webhook"], mock_context)
        endpoint = mock_context.bridge.post.call_args[0][0]
        assert endpoint == "setup/waha-webhook"

    def test_setup_webhook_api_error(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context.bridge.post.side_effect = APIError(status_code=400, detail="Bad webhook URL")
        result = invoke(runner, ["bridge", "setup-webhook"], mock_context)
        assert result.exit_code == 1

    def test_setup_webhook_json_mode(self, runner: CliRunner, mock_context: AppContext) -> None:
        mock_context._output = Output(json_mode=True, quiet=True, format="json")
        mock_context.bridge.post.return_value = {"status": "ok"}
        result = invoke(runner, ["bridge", "setup-webhook"], mock_context)
        assert result.exit_code == 0
