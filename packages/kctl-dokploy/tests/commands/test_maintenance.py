"""Tests for maintenance commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()


def _extract_json(output: str) -> str:
    """Extract JSON block from output that may contain INFO/WARN prefix lines."""
    lines = output.strip().splitlines()
    # Find the first line that starts a JSON value
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") or stripped.startswith("{"):
            return "\n".join(lines[i:])
    return output


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


def _setup_clean_mock(mock_client: MagicMock) -> None:
    """Configure mock_client for a clean system (no issues)."""

    def get_side_effect(endpoint, **kwargs):
        if endpoint == "/project.all":
            return [
                {
                    "projectId": "p-1",
                    "name": "main",
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
        if endpoint == "/backup.all":
            return []
        if endpoint == "/docker.getContainers":
            return [{"containerId": "c1", "name": "web_1", "state": "running"}]
        return []

    mock_client.get.side_effect = get_side_effect


class TestMaintenanceIntegrity:
    def test_integrity_json_returns_list(self, mock_client: MagicMock) -> None:
        _setup_clean_mock(mock_client)
        result = runner.invoke(app, ["--json", "maintenance", "integrity"])
        assert result.exit_code == 0
        data = json.loads(_extract_json(result.output))
        assert isinstance(data, list)

    def test_integrity_no_issues_when_clean(self, mock_client: MagicMock) -> None:
        _setup_clean_mock(mock_client)
        result = runner.invoke(app, ["--json", "maintenance", "integrity"])
        assert result.exit_code == 0
        data = json.loads(_extract_json(result.output))
        # With clean system, should have no critical findings
        critical = [f for f in data if f["severity"] == "critical"]
        assert len(critical) == 0

    def test_integrity_with_error_service_exits_1(self, mock_client: MagicMock) -> None:
        def get_side_effect(endpoint, **kwargs):
            if endpoint == "/project.all":
                return [
                    {
                        "projectId": "p-1",
                        "name": "main",
                        "compose": [{"composeId": "c-1", "name": "web", "composeStatus": "error"}],
                        "applications": [],
                    }
                ]
            if endpoint == "/deployment.all":
                return []
            if endpoint == "/backup.all":
                return []
            return []

        mock_client.get.side_effect = get_side_effect
        # In JSON mode, exit code is 0 but critical findings are in the data
        result = runner.invoke(app, ["--json", "maintenance", "integrity"])
        assert result.exit_code == 0
        data = json.loads(_extract_json(result.output))
        critical = [f for f in data if f["severity"] == "critical"]
        assert len(critical) > 0

    def test_integrity_pretty_exits_1_with_critical(self, mock_client: MagicMock) -> None:
        """Pretty mode exits 1 when critical findings exist."""

        def get_side_effect(endpoint, **kwargs):
            if endpoint == "/project.all":
                return [
                    {
                        "projectId": "p-1",
                        "name": "main",
                        "compose": [{"composeId": "c-1", "name": "web", "composeStatus": "error"}],
                        "applications": [],
                    }
                ]
            if endpoint == "/deployment.all":
                return []
            if endpoint == "/backup.all":
                return []
            return []

        mock_client.get.side_effect = get_side_effect
        result = runner.invoke(app, ["maintenance", "integrity"])
        assert result.exit_code == 1

    def test_integrity_finding_structure(self, mock_client: MagicMock) -> None:
        _setup_clean_mock(mock_client)
        result = runner.invoke(app, ["--json", "maintenance", "integrity"])
        assert result.exit_code == 0
        data = json.loads(_extract_json(result.output))
        for finding in data:
            assert "category" in finding
            assert "name" in finding
            assert "severity" in finding
            assert "issue" in finding
