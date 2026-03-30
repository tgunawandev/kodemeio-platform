"""Tests for project commands using Typer's CliRunner."""

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
    """Patch AppContext.client to return our mock."""
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestProjectsList:
    def test_list_json(self, mock_client: MagicMock, sample_projects: list[dict]) -> None:
        mock_client.get.return_value = sample_projects
        result = runner.invoke(app, ["--json", "projects", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_list_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "projects", "list"])
        assert result.exit_code == 0


class TestProjectsGet:
    def test_get_by_name(self, mock_client: MagicMock, sample_projects: list[dict]) -> None:
        mock_client.get.return_value = sample_projects
        result = runner.invoke(app, ["--json", "projects", "get", "kodemeio"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "kodemeio"

    def test_get_not_found(self, mock_client: MagicMock, sample_projects: list[dict]) -> None:
        mock_client.get.return_value = sample_projects
        result = runner.invoke(app, ["projects", "get", "nonexistent"])
        assert result.exit_code == 1
