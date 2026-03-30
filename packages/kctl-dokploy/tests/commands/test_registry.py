"""Tests for registry commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()

SAMPLE_REGISTRIES = [
    {
        "registryId": "reg-aaa-111",
        "registryName": "ghcr",
        "registryUrl": "ghcr.io",
        "username": "kodemeio",
        "registryType": "github",
        "createdAt": "2026-01-01T00:00:00Z",
    },
    {
        "registryId": "reg-bbb-222",
        "registryName": "local-registry",
        "registryUrl": "registry.kodeme.io",
        "username": "admin",
        "registryType": "selfHosted",
        "createdAt": "2026-02-01T00:00:00Z",
    },
]


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestRegistryList:
    def test_list_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_REGISTRIES
        result = runner.invoke(app, ["--json", "registry", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["registryName"] == "ghcr"

    def test_list_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "registry", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []


class TestRegistryGet:
    def test_get_registry_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_REGISTRIES[0]
        result = runner.invoke(app, ["--json", "registry", "get", "reg-aaa-111"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["registryName"] == "ghcr"

    def test_get_not_found_exits_1(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = "not a dict"
        result = runner.invoke(app, ["registry", "get", "nonexistent"])
        assert result.exit_code == 1


class TestRegistryRemove:
    def test_remove_with_force(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["registry", "remove", "reg-bbb-222", "--force"])
        assert result.exit_code == 0

    def test_remove_prompts_without_force(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["registry", "remove", "reg-bbb-222"], input="y\n")
        assert result.exit_code == 0


class TestRegistryTest:
    def test_test_connection_success(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["registry", "test", "reg-aaa-111"])
        assert result.exit_code == 0
