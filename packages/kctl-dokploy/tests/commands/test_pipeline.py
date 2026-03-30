"""Tests for pipeline commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()

SAMPLE_COMPOSE_DATA = {
    "composeId": "comp-xyz-789",
    "name": "web-app",
    "composeStatus": "done",
    "sourceType": "raw",
    "createdAt": "2026-01-15T10:00:00Z",
    "updatedAt": "2026-03-20T14:30:00Z",
    "description": "Main web service",
    "domains": [
        {
            "domainId": "dom-001",
            "host": "web.kodeme.io",
            "port": 3000,
            "https": True,
            "certificateType": "letsencrypt",
        }
    ],
}

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
        "status": "done",
        "deploymentType": "manual",
        "createdAt": "2026-03-19T08:00:00Z",
        "endedAt": "2026-03-19T08:03:00Z",
        "title": "Deploy v1.2.2",
    },
]


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestPipelineStatus:
    def test_status_json(self, mock_client: MagicMock) -> None:
        def get_side_effect(endpoint, **kwargs):
            if endpoint == "/compose.one":
                return SAMPLE_COMPOSE_DATA
            if endpoint == "/deployment.allByCompose":
                return SAMPLE_DEPLOYMENTS
            return []

        mock_client.get.side_effect = get_side_effect
        result = runner.invoke(app, ["--json", "pipeline", "status", "comp-xyz-789"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "web-app"
        assert data["composeStatus"] == "done"

    def test_status_not_found_exits_1(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = "not a dict"
        result = runner.invoke(app, ["pipeline", "status", "nonexistent"])
        assert result.exit_code == 1


class TestPipelineHistory:
    def test_history_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_DEPLOYMENTS
        result = runner.invoke(app, ["--json", "pipeline", "history", "comp-xyz-789"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_history_empty_exits_1(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = "not a list"
        result = runner.invoke(app, ["pipeline", "history", "comp-xyz-789"])
        assert result.exit_code == 1

    def test_history_with_limit(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_DEPLOYMENTS
        result = runner.invoke(app, ["--json", "pipeline", "history", "comp-xyz-789", "--limit", "1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1


class TestPipelineVerify:
    def test_verify_healthy_compose_json(self, mock_client: MagicMock) -> None:
        with patch("kctl_dokploy.commands.pipeline.quick_health_check", return_value="done"):
            result = runner.invoke(app, ["--json", "pipeline", "verify", "comp-xyz-789"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["composeStatus"] == "done"
        assert data["apiHealthy"] is True
        assert data["overall"] == "healthy"

    def test_verify_unhealthy_compose_exits_1(self, mock_client: MagicMock) -> None:
        with patch("kctl_dokploy.commands.pipeline.quick_health_check", return_value="error"):
            result = runner.invoke(app, ["pipeline", "verify", "comp-xyz-789"])
        assert result.exit_code == 1
