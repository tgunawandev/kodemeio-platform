"""Tests for status commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestStatusHealth:
    def test_health_json_healthy(self, mock_client: MagicMock) -> None:
        mock_client.check_health.return_value = 200
        result = runner.invoke(app, ["--json", "status", "health"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "healthy"
        assert data["http_code"] == 200

    def test_health_json_unhealthy(self, mock_client: MagicMock) -> None:
        mock_client.check_health.return_value = 503
        result = runner.invoke(app, ["--json", "status", "health"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "unhealthy"
        assert data["http_code"] == 503

    def test_health_pretty_exits_1_when_unhealthy(self, mock_client: MagicMock) -> None:
        mock_client.check_health.return_value = 503
        result = runner.invoke(app, ["status", "health"])
        assert result.exit_code == 1
