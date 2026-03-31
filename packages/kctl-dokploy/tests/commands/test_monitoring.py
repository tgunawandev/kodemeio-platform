"""Tests for monitoring commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()

SAMPLE_CONTAINERS = [
    {
        "name": "web_app_1",
        "image": "nginx:latest",
        "state": "running",
        "status": "Up 2 days",
        "ports": "80/tcp",
    },
    {
        "name": "db_postgres_1",
        "image": "postgres:16",
        "state": "running",
        "status": "Up 5 days",
        "ports": "5432/tcp",
    },
]


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestMonitoringContainers:
    def test_containers_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_CONTAINERS
        result = runner.invoke(app, ["--json", "monitoring", "containers"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        # The command passes data_for_json as the raw data
        assert isinstance(data, list)
        assert len(data) == 2

    def test_containers_empty_returns_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "monitoring", "containers"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_containers_non_list_response(self, mock_client: MagicMock) -> None:
        # If API returns a dict with containers key
        mock_client.get.return_value = {"containers": SAMPLE_CONTAINERS}
        result = runner.invoke(app, ["--json", "monitoring", "containers"])
        assert result.exit_code == 0


class TestMonitoringResources:
    def test_resources_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "cpuUsage": "25%",
            "memoryUsage": "4.2 GB",
            "diskUsage": "120 GB",
            "totalMemory": "16 GB",
            "totalDisk": "500 GB",
        }
        result = runner.invoke(app, ["--json", "monitoring", "resources"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_resources_api_failure_returns_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.side_effect = Exception("API error")
        result = runner.invoke(app, ["--json", "monitoring", "resources"])
        assert result.exit_code == 0
        # Empty dict data_for_json produces no JSON output (kctl-lib behavior)
        if result.output.strip():
            data = json.loads(result.output)
            assert isinstance(data, dict)
