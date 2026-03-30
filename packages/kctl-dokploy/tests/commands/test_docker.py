"""Tests for docker commands."""

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
        "containerId": "abc123def456",
        "name": "web_app_1",
        "state": "running",
        "image": "nginx:latest",
    },
    {
        "containerId": "xyz789uvw012",
        "name": "db_postgres_1",
        "state": "running",
        "image": "postgres:16",
    },
]

SAMPLE_IMAGES = [
    {
        "id": "sha256:aabbcc112233",
        "tags": ["nginx:latest"],
        "size": 57344000,
    },
    {
        "id": "sha256:ddeeff445566",
        "tags": ["postgres:16"],
        "size": 134217728,
    },
]


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestDockerContainers:
    def test_containers_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_CONTAINERS
        result = runner.invoke(app, ["--json", "docker", "containers"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["state"] == "running"

    def test_containers_empty_returns_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "docker", "containers"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []

    def test_containers_with_server_filter(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_CONTAINERS
        result = runner.invoke(app, ["--json", "docker", "containers", "--server", "srv-001"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)


class TestDockerImages:
    def test_images_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_IMAGES
        result = runner.invoke(app, ["--json", "docker", "images"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_images_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "docker", "images"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []


class TestDockerStats:
    def test_stats_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "images": "2.1 GB",
            "containers": "500 MB",
            "volumes": "1.2 GB",
            "buildCache": "300 MB",
            "total": "4.1 GB",
        }
        result = runner.invoke(app, ["--json", "docker", "stats"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "images" in data

    def test_stats_empty_dict_ok(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {}
        result = runner.invoke(app, ["--json", "docker", "stats"])
        assert result.exit_code == 0
        # Empty dict data_for_json produces no JSON output (kctl-common behavior)
        if result.output.strip():
            data = json.loads(result.output)
            assert isinstance(data, dict)


class TestDockerPrune:
    def test_prune_with_force(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["docker", "prune", "--force"])
        assert result.exit_code == 0
