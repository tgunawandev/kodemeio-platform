"""Tests for diagnose commands."""

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


def _setup_healthy_mock(mock_client: MagicMock) -> None:
    """Configure mock_client to return healthy responses for all diagnostic API calls."""

    def get_side_effect(endpoint, **kwargs):
        if endpoint == "/project.all":
            return [
                {
                    "projectId": "p-1",
                    "name": "prod",
                    "compose": [{"composeId": "c-1", "name": "web", "composeStatus": "done"}],
                    "applications": [],
                }
            ]
        if endpoint == "/deployment.all":
            return [
                {
                    "deploymentId": "d-1",
                    "status": "done",
                    "createdAt": "2026-03-20T10:00:00Z",
                }
            ]
        if endpoint == "/certificate.all":
            return []
        if endpoint == "/docker.getContainers":
            return [{"containerId": "c1", "name": "web_1", "state": "running"}]
        if endpoint == "/backup.all":
            return []
        if endpoint == "/server.all":
            return []
        if endpoint == "/notification.all":
            return [{"notificationId": "n1", "name": "slack", "enabled": True}]
        return []

    mock_client.check_health.return_value = 200
    mock_client.get.side_effect = get_side_effect


class TestDiagnoseRun:
    def test_run_json_returns_report_structure(self, mock_client: MagicMock) -> None:
        _setup_healthy_mock(mock_client)
        result = runner.invoke(app, ["--json", "diagnose", "run"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "overall_score" in data
        assert "sections" in data
        assert isinstance(data["sections"], list)
        assert len(data["sections"]) == 8

    def test_run_score_is_valid_range(self, mock_client: MagicMock) -> None:
        _setup_healthy_mock(mock_client)
        result = runner.invoke(app, ["--json", "diagnose", "run"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        score = data["overall_score"]
        assert 0 <= score <= 100

    def test_run_sections_have_required_fields(self, mock_client: MagicMock) -> None:
        _setup_healthy_mock(mock_client)
        result = runner.invoke(app, ["--json", "diagnose", "run"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        for section in data["sections"]:
            assert "name" in section
            assert "score" in section
            assert "findings" in section
            assert "weight" in section

    def test_run_api_failure_still_completes(self, mock_client: MagicMock) -> None:
        # Even with API failures diagnose should complete and report low score
        mock_client.check_health.return_value = 503
        mock_client.get.side_effect = Exception("Connection refused")
        result = runner.invoke(app, ["--json", "diagnose", "run"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "overall_score" in data


class TestDiagnoseSection:
    def test_run_single_section_api_health(self, mock_client: MagicMock) -> None:
        mock_client.check_health.return_value = 200
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "diagnose", "section", "api_health"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "overall_score" in data
        assert len(data["sections"]) == 1
        assert data["sections"][0]["name"] == "api_health"

    def test_run_single_section_unknown_exits_1(self, mock_client: MagicMock) -> None:
        result = runner.invoke(app, ["diagnose", "section", "nonexistent_section"])
        assert result.exit_code == 1
