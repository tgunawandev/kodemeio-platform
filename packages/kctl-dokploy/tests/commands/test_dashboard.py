"""Tests for dashboard commands."""

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


class TestDashboardShow:
    def test_show_json_with_projects(
        self, mock_client: MagicMock, sample_projects: list[dict], sample_servers: list[dict]
    ) -> None:
        def get_side_effect(endpoint, **kwargs):
            if endpoint == "/project.all":
                return sample_projects
            if endpoint == "/server.all":
                return sample_servers
            return []

        mock_client.get.side_effect = get_side_effect
        result = runner.invoke(app, ["--json", "dashboard", "show"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "projects" in data
        assert data["projects"] == 2
        assert "servers" in data
        assert data["servers"] == 2

    def test_show_json_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "dashboard", "show"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["projects"] == 0
        assert data["total_services"] == 0

    def test_show_counts_compose_and_apps(self, mock_client: MagicMock, sample_projects: list[dict]) -> None:
        def get_side_effect(endpoint, **kwargs):
            if endpoint == "/project.all":
                return sample_projects
            return []

        mock_client.get.side_effect = get_side_effect
        result = runner.invoke(app, ["--json", "dashboard", "show"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        # sample_projects has 2 compose services and 1 application
        assert data["compose_services"] == 2
        assert data["applications"] == 1
        assert data["total_services"] == 3

    def test_show_handles_api_failure_gracefully(self, mock_client: MagicMock) -> None:
        mock_client.get.side_effect = Exception("API down")
        result = runner.invoke(app, ["--json", "dashboard", "show"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["projects"] == 0
