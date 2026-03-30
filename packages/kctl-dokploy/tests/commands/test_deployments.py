"""Tests for deployments commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()

SAMPLE_DEPLOYMENTS = [
    {
        "deploymentId": "dep-aaa-111",
        "status": "done",
        "deploymentType": "push",
        "createdAt": "2026-03-20T10:00:00Z",
        "endedAt": "2026-03-20T10:05:00Z",
        "title": "Deploy v1.2.3",
    },
    {
        "deploymentId": "dep-bbb-222",
        "status": "error",
        "deploymentType": "manual",
        "createdAt": "2026-03-19T08:00:00Z",
        "endedAt": "2026-03-19T08:02:00Z",
        "title": "Deploy v1.2.2",
    },
]


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestDeploymentsList:
    def test_list_all_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_DEPLOYMENTS
        result = runner.invoke(app, ["--json", "deployments", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_list_empty_returns_empty_list(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "deployments", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []

    def test_list_filter_by_compose(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_DEPLOYMENTS[:1]
        result = runner.invoke(app, ["--json", "deployments", "list", "--compose", "comp-xyz-789"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1

    def test_list_filter_by_application(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_DEPLOYMENTS[:1]
        result = runner.invoke(app, ["--json", "deployments", "list", "--application", "app-111-222"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1

    def test_list_with_limit(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_DEPLOYMENTS
        result = runner.invoke(app, ["--json", "deployments", "list", "--limit", "1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1


class TestDeploymentsGet:
    def test_get_deployment_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_DEPLOYMENTS[0]
        result = runner.invoke(app, ["--json", "deployments", "get", "dep-aaa-111"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "done"
        assert data["deploymentId"] == "dep-aaa-111"

    def test_get_not_found_exits_1(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = "not a dict"
        result = runner.invoke(app, ["deployments", "get", "nonexistent"])
        assert result.exit_code == 1


class TestDeploymentsMisc:
    def test_redeploy_triggers_successfully(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["deployments", "redeploy", "comp-xyz-789"])
        assert result.exit_code == 0

    def test_cancel_deployment(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["deployments", "cancel", "dep-aaa-111"])
        assert result.exit_code == 0
