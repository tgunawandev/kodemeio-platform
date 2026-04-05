"""Tests for kctl-waha health commands."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_lib.exceptions import APIError
from kctl_waha.cli import app
from kctl_waha.commands.health import _check_health
from kctl_waha.core.callbacks import AppContext
from kctl_waha.core.client import BridgeClient, WahaClient
from kctl_lib.output import Output


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


class TestCheckHealthFunction:
    """Unit tests for the _check_health() helper — called directly with a mock AppContext."""

    def test_all_healthy(self, mock_context: AppContext) -> None:
        mock_context.client.check_health.return_value = {"status": "ok", "version": "2024.1.0"}
        mock_context.client.get.return_value = [{"name": "default", "status": "WORKING"}]
        mock_context.bridge.check_health.return_value = {"status": "ok"}

        results = _check_health(mock_context)
        assert results["waha_health"] is True
        assert results["active_sessions"] is True
        assert results["session_count"] == 1
        assert results["bridge_health"] is True
        assert results["server_version"] == "2024.1.0"
        assert results["score"] == 100

    def test_no_active_sessions(self, mock_context: AppContext) -> None:
        mock_context.client.check_health.return_value = {"status": "ok", "version": "2024.1.0"}
        mock_context.client.get.return_value = [{"name": "s1", "status": "STOPPED"}]
        mock_context.bridge.check_health.return_value = {"status": "ok"}

        results = _check_health(mock_context)
        assert results["active_sessions"] is False
        assert results["session_count"] == 0
        assert results["score"] == 70  # 30 waha + 20 version + 20 bridge

    def test_waha_health_empty_response(self, mock_context: AppContext) -> None:
        mock_context.client.check_health.return_value = {}
        mock_context.client.get.return_value = [{"name": "s1", "status": "WORKING"}]
        mock_context.bridge.check_health.return_value = {"status": "ok"}

        results = _check_health(mock_context)
        assert results["waha_health"] is False

    def test_waha_health_exception(self, mock_context: AppContext) -> None:
        mock_context.client.check_health.side_effect = Exception("Connection refused")
        mock_context.client.get.return_value = []
        mock_context.bridge.check_health.return_value = {}

        results = _check_health(mock_context)
        assert results["waha_health"] is False

    def test_bridge_health_empty_response(self, mock_context: AppContext) -> None:
        mock_context.client.check_health.return_value = {"status": "ok", "version": "v1"}
        mock_context.client.get.return_value = [{"name": "s1", "status": "WORKING"}]
        mock_context.bridge.check_health.return_value = {}

        results = _check_health(mock_context)
        assert results["bridge_health"] is False
        assert results["score"] == 80  # 30 waha + 30 sessions + 20 version

    def test_bridge_health_exception(self, mock_context: AppContext) -> None:
        mock_context.client.check_health.return_value = {"status": "ok"}
        mock_context.client.get.return_value = []
        mock_context.bridge.check_health.side_effect = Exception("Bridge down")

        results = _check_health(mock_context)
        assert results["bridge_health"] is False

    def test_sessions_api_exception(self, mock_context: AppContext) -> None:
        mock_context.client.check_health.return_value = {"status": "ok", "version": "v1"}
        mock_context.client.get.side_effect = APIError(status_code=503, detail="Unavailable")
        mock_context.bridge.check_health.return_value = {"status": "ok"}

        results = _check_health(mock_context)
        assert results["active_sessions"] is False

    def test_version_from_server_version_endpoint(self, mock_context: AppContext) -> None:
        """If check_health has no version key, fall back to server/version endpoint."""
        mock_context.client.check_health.return_value = {"status": "ok"}

        def get_side_effect(endpoint: str, **kwargs: object) -> object:
            if "server/version" in endpoint:
                return {"version": "2024.2.0"}
            return []

        mock_context.client.get.side_effect = get_side_effect
        mock_context.bridge.check_health.return_value = {"status": "ok"}

        results = _check_health(mock_context)
        assert results["server_version"] == "2024.2.0"

    def test_server_version_unavailable(self, mock_context: AppContext) -> None:
        mock_context.client.check_health.return_value = {"status": "ok"}
        mock_context.client.get.return_value = []
        mock_context.bridge.check_health.return_value = {}

        results = _check_health(mock_context)
        assert results["server_version"] is None
        assert results["score"] == 30  # only waha health

    def test_score_zero_all_failing(self, mock_context: AppContext) -> None:
        mock_context.client.check_health.return_value = {}
        mock_context.client.get.return_value = []
        mock_context.bridge.check_health.return_value = {}

        results = _check_health(mock_context)
        assert results["score"] == 0

    def test_multiple_sessions_counts_only_working(self, mock_context: AppContext) -> None:
        mock_context.client.check_health.return_value = {"status": "ok", "version": "v1"}
        mock_context.client.get.return_value = [
            {"name": "s1", "status": "WORKING"},
            {"name": "s2", "status": "WORKING"},
            {"name": "s3", "status": "STOPPED"},
        ]
        mock_context.bridge.check_health.return_value = {"status": "ok"}

        results = _check_health(mock_context)
        assert results["session_count"] == 2
        assert results["total_sessions"] == 3
        assert results["active_sessions"] is True

    def test_score_does_not_exceed_100(self, mock_context: AppContext) -> None:
        mock_context.client.check_health.return_value = {"status": "ok", "version": "v1"}
        mock_context.client.get.return_value = [{"name": "s", "status": "WORKING"}]
        mock_context.bridge.check_health.return_value = {"status": "ok"}

        results = _check_health(mock_context)
        assert results["score"] <= 100


class TestHealthCommand:
    def test_health_all_ok_exits_zero(self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock) -> None:
        mock_client.check_health.return_value = {"status": "ok", "version": "2024.1.0"}
        mock_client.get.return_value = [{"name": "default", "status": "WORKING"}]
        mock_bridge.check_health.return_value = {"status": "ok"}

        result = invoke(runner, ["health"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_health_low_score_exits_one(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.check_health.return_value = {}
        mock_client.get.return_value = []
        mock_bridge.check_health.return_value = {}

        result = invoke(runner, ["health"], mock_client, mock_bridge)
        assert result.exit_code == 1

    def test_health_score_below_50_exits_one(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        # 30pts (waha only), < 50 → exit 1
        mock_client.check_health.return_value = {"status": "ok"}
        mock_client.get.return_value = []
        mock_bridge.check_health.return_value = {}

        result = invoke(runner, ["health"], mock_client, mock_bridge)
        assert result.exit_code == 1

    def test_health_score_50_exits_zero(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        # 30 waha + 20 version = 50 pts → exit 0
        mock_client.check_health.return_value = {"status": "ok", "version": "v1"}
        mock_client.get.return_value = []
        mock_bridge.check_health.return_value = {}

        result = invoke(runner, ["health"], mock_client, mock_bridge)
        assert result.exit_code == 0

    def test_health_score_80_exits_zero(
        self, runner: CliRunner, mock_client: MagicMock, mock_bridge: MagicMock
    ) -> None:
        mock_client.check_health.return_value = {"status": "ok", "version": "v1"}
        mock_client.get.return_value = [{"name": "s1", "status": "WORKING"}]
        mock_bridge.check_health.return_value = {}

        result = invoke(runner, ["health"], mock_client, mock_bridge)
        assert result.exit_code == 0
