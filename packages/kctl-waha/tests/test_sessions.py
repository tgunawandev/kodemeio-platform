"""Tests for kctl-waha sessions commands."""

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
    """Patch WahaClient and BridgeClient constructors in callbacks."""
    with patch("kctl_waha.core.callbacks.resolve_connection", return_value=("https://waha.test", "testkey")):
        with patch("kctl_waha.core.callbacks.resolve_bridge_url", return_value="http://bridge.test"):
            with patch("kctl_waha.core.callbacks.WahaClient", return_value=mock_client):
                with patch("kctl_waha.core.callbacks.BridgeClient", return_value=mock_bridge):
                    yield


def invoke(runner: CliRunner, args: list[str], mock_client: MagicMock, mock_bridge: MagicMock) -> object:
    with patched_clients(mock_client, mock_bridge):
        return runner.invoke(app, args)


class TestSessionsList:
    def test_list_sessions_empty(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = []
        result = invoke(runner, ["sessions", "list"], mock_client, mock_bridge)
        assert result.exit_code == 0
        mock_client.get.assert_called_once_with("sessions/", params={})

    def test_list_sessions_with_working(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.get.return_value = [
            {"name": "default", "status": "WORKING", "config": {"engine": "NOWEB"}},
            {"name": "second", "status": "STOPPED", "config": {"engine": "WEBJS"}},
        ]
        result = invoke(runner, ["sessions", "list"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_list_all_flag_passes_param(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.get.return_value = []
        result = invoke(runner, ["sessions", "list", "--all"], mock_client, mock_bridge)
        assert result.exit_code == 0
        mock_client.get.assert_called_once_with("sessions/", params={"all": "true"})

    def test_list_sessions_api_error(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.side_effect = APIError(status_code=500, detail="Server error")
        result = invoke(runner, ["sessions", "list"], mock_client, mock_bridge)
        assert result.exit_code == 1

    def test_list_sessions_non_list_response(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.get.return_value = {"error": "unexpected"}
        result = invoke(runner, ["sessions", "list"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_list_sessions_various_statuses(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.get.return_value = [
            {"name": "s1", "status": "WORKING", "config": {"engine": "NOWEB"}},
            {"name": "s2", "status": "SCAN_QR_CODE", "config": {"engine": "NOWEB"}},
            {"name": "s3", "status": "STARTING", "config": {"engine": "NOWEB"}},
            {"name": "s4", "status": "FAILED", "config": {"engine": "WEBJS"}},
            {"name": "s5", "status": "STOPPED", "engine": "NOWEB"},
        ]
        result = invoke(runner, ["sessions", "list"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_list_sessions_unknown_status(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.get.return_value = [
            {"name": "s1", "status": "WEIRD_STATUS", "config": {}},
        ]
        result = invoke(runner, ["sessions", "list"], mock_client, mock_bridge)
        assert result.exit_code == 0


class TestSessionsGet:
    def test_get_found(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = [
            {"name": "default", "status": "WORKING", "config": {"engine": "NOWEB", "webhooks": []}}
        ]
        result = invoke(runner, ["sessions", "get", "default"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_get_not_found(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = [{"name": "other", "status": "WORKING", "config": {}}]
        result = invoke(runner, ["sessions", "get", "missing"], mock_client, mock_bridge)
        assert result.exit_code == 1

    def test_get_with_me_info_when_working(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        def get_side_effect(endpoint: str, **kwargs: object) -> object:
            if "me" in endpoint:
                return {"id": "6281234@c.us", "pushName": "Test User", "platform": "android"}
            return [{"name": "default", "status": "WORKING", "config": {"engine": "NOWEB"}}]

        mock_client.get.side_effect = get_side_effect
        result = invoke(runner, ["sessions", "get", "default"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_get_with_webhooks(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = [
            {
                "name": "default",
                "status": "STOPPED",
                "config": {
                    "engine": "NOWEB",
                    "webhooks": [{"url": "https://hook.example.com", "events": ["message"]}],
                },
            }
        ]
        result = invoke(runner, ["sessions", "get", "default"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_get_with_proxy_and_debug(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = [
            {
                "name": "default",
                "status": "STOPPED",
                "config": {
                    "engine": "NOWEB",
                    "proxy": "http://proxy.example.com",
                    "debug": True,
                },
            }
        ]
        result = invoke(runner, ["sessions", "get", "default"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_get_api_error(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.side_effect = APIError(status_code=503, detail="Unavailable")
        result = invoke(runner, ["sessions", "get", "default"], mock_client, mock_bridge)
        assert result.exit_code == 1


class TestSessionsStart:
    def test_start_existing_session(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = [{"name": "default", "status": "STOPPED", "config": {}}]
        mock_client.post.return_value = {"status": "STARTING"}
        result = invoke(runner, ["sessions", "start", "default"], mock_client, mock_bridge)
        assert result.exit_code == 0
        mock_client.post.assert_called_once_with("sessions/default/start")

    def test_start_new_session(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = []
        mock_client.post.return_value = {"name": "new", "status": "STARTING"}
        result = invoke(runner, ["sessions", "start", "new"], mock_client, mock_bridge)
        assert result.exit_code == 0
        mock_client.post.assert_called_once_with("sessions/", data={"name": "new"})

    def test_start_with_engine(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = []
        mock_client.post.return_value = {"status": "STARTING"}
        result = invoke(runner, ["sessions", "start", "new", "--engine", "webjs"], mock_client, mock_bridge)
        assert result.exit_code == 0
        mock_client.post.assert_called_once_with("sessions/", data={"name": "new", "config": {"engine": "WEBJS"}})

    def test_start_engine_uppercased(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = []
        mock_client.post.return_value = {}
        invoke(runner, ["sessions", "start", "s", "--engine", "noweb"], mock_client, mock_bridge)
        call_data = mock_client.post.call_args[1]["data"]
        assert call_data["config"]["engine"] == "NOWEB"

    def test_start_api_error(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = []
        mock_client.post.side_effect = APIError(status_code=400, detail="Bad request")
        result = invoke(runner, ["sessions", "start", "bad"], mock_client, mock_bridge)
        assert result.exit_code == 1

    def test_start_returns_status(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = []
        mock_client.post.return_value = {"status": "SCAN_QR_CODE"}
        result = invoke(runner, ["sessions", "start", "new"], mock_client, mock_bridge)
        assert result.exit_code == 0


class TestSessionsStop:
    def test_stop_success(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = invoke(runner, ["sessions", "stop", "default"], mock_client, mock_bridge)
        assert result.exit_code == 0
        mock_client.post.assert_called_once_with("sessions/default/stop")

    def test_stop_api_error(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.post.side_effect = APIError(status_code=404, detail="Not found")
        result = invoke(runner, ["sessions", "stop", "missing"], mock_client, mock_bridge)
        assert result.exit_code == 1

    def test_stop_default_session(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = invoke(runner, ["sessions", "stop"], mock_client, mock_bridge)
        assert result.exit_code == 0


class TestSessionsRestart:
    def test_restart_calls_stop_then_start(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.post.return_value = {}
        result = invoke(runner, ["sessions", "restart", "default"], mock_client, mock_bridge)
        assert result.exit_code == 0
        assert mock_client.post.call_count == 2
        calls = [c.args[0] for c in mock_client.post.call_args_list]
        assert "sessions/default/stop" in calls
        assert "sessions/default/start" in calls

    def test_restart_continues_if_stop_fails(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        def post_side_effect(endpoint: str, **kwargs: object) -> object:
            if "stop" in endpoint:
                raise APIError(status_code=404, detail="Already stopped")
            return {}

        mock_client.post.side_effect = post_side_effect
        result = invoke(runner, ["sessions", "restart", "default"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_restart_fails_if_start_fails(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        stop_called = {"done": False}

        def post_side_effect(endpoint: str, **kwargs: object) -> object:
            if "stop" in endpoint:
                stop_called["done"] = True
                return {}
            raise APIError(status_code=500, detail="Start failed")

        mock_client.post.side_effect = post_side_effect
        result = invoke(runner, ["sessions", "restart", "default"], mock_client, mock_bridge)
        assert result.exit_code == 1
        assert stop_called["done"]


class TestSessionsLogout:
    def test_logout_force(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = invoke(runner, ["sessions", "logout", "default", "--force"], mock_client, mock_bridge)
        assert result.exit_code == 0
        mock_client.post.assert_called_once_with("sessions/default/logout")

    def test_logout_api_error(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.post.side_effect = APIError(status_code=400, detail="Bad")
        result = invoke(runner, ["sessions", "logout", "default", "--force"], mock_client, mock_bridge)
        assert result.exit_code == 1

    def test_logout_no_force_decline(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        with patched_clients(mock_client, mock_bridge):
            result = runner.invoke(app, ["sessions", "logout", "default"], input="n\n")
        assert result.exit_code == 0
        mock_client.post.assert_not_called()

    def test_logout_no_force_confirm(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.post.return_value = {}
        with patched_clients(mock_client, mock_bridge):
            result = runner.invoke(app, ["sessions", "logout", "default"], input="y\n")
        assert result.exit_code == 0
        mock_client.post.assert_called_once_with("sessions/default/logout")


class TestSessionsDelete:
    def test_delete_force(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.delete.return_value = {}
        result = invoke(runner, ["sessions", "delete", "old", "--force"], mock_client, mock_bridge)
        assert result.exit_code == 0
        mock_client.delete.assert_called_once_with("sessions/old")

    def test_delete_api_error(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.delete.side_effect = APIError(status_code=404, detail="Not found")
        result = invoke(runner, ["sessions", "delete", "old", "--force"], mock_client, mock_bridge)
        assert result.exit_code == 1

    def test_delete_decline_confirmation(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        with patched_clients(mock_client, mock_bridge):
            result = runner.invoke(app, ["sessions", "delete", "old"], input="n\n")
        assert result.exit_code == 0
        mock_client.delete.assert_not_called()

    def test_delete_confirm(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.delete.return_value = {}
        with patched_clients(mock_client, mock_bridge):
            result = runner.invoke(app, ["sessions", "delete", "old"], input="y\n")
        assert result.exit_code == 0
        mock_client.delete.assert_called_once_with("sessions/old")


class TestSessionsQr:
    def test_qr_with_value(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = {"value": "some-qr-data"}
        result = invoke(runner, ["sessions", "qr", "default"], mock_client, mock_bridge)
        assert result.exit_code == 0
        mock_client.get.assert_called_once_with("sessions/default/auth/qr")

    def test_qr_empty_value(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = {"value": ""}
        result = invoke(runner, ["sessions", "qr", "default"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_qr_api_error(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.side_effect = APIError(status_code=404, detail="No QR")
        result = invoke(runner, ["sessions", "qr", "default"], mock_client, mock_bridge)
        assert result.exit_code == 1

    def test_qr_unexpected_format(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = "plain string"
        result = invoke(runner, ["sessions", "qr", "default"], mock_client, mock_bridge)
        assert result.exit_code == 1

    def test_qr_default_session(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = {"value": "qr-data"}
        result = invoke(runner, ["sessions", "qr"], mock_client, mock_bridge)
        assert result.exit_code == 0


class TestSessionsMe:
    def test_me_success(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = {
            "id": "6281234567890@c.us",
            "pushName": "Test User",
            "platform": "android",
        }
        result = invoke(runner, ["sessions", "me", "default"], mock_client, mock_bridge)
        assert result.exit_code == 0
        mock_client.get.assert_called_once_with("sessions/default/me")

    def test_me_api_error(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.side_effect = APIError(status_code=401, detail="Unauthorized")
        result = invoke(runner, ["sessions", "me", "default"], mock_client, mock_bridge)
        assert result.exit_code == 1

    def test_me_unexpected_format(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = ["unexpected", "list"]
        result = invoke(runner, ["sessions", "me", "default"], mock_client, mock_bridge)
        assert result.exit_code == 1

    def test_me_empty_fields(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = {"id": "", "pushName": "", "platform": ""}
        result = invoke(runner, ["sessions", "me"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_me_strips_c_us_from_id(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.get.return_value = {
            "id": "6281234567890@c.us",
            "pushName": "User",
            "platform": "ios",
        }
        result = invoke(runner, ["sessions", "me", "s1"], mock_client, mock_bridge)
        assert result.exit_code == 0
