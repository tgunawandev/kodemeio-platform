"""Tests for env commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()

ENV_STRING = "DATABASE_URL=postgres://localhost/mydb\nREDIS_URL=redis://localhost:6379\nDEBUG=false"


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestEnvList:
    def test_list_env_from_string_response(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"environment": ENV_STRING}
        result = runner.invoke(app, ["--json", "env", "list", "comp-xyz-789"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)
        assert "environment" in data

    def test_list_env_string_directly(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = ENV_STRING
        result = runner.invoke(app, ["env", "list", "comp-xyz-789"])
        assert result.exit_code == 0

    def test_list_empty_env(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"environment": ""}
        result = runner.invoke(app, ["--json", "env", "list", "comp-xyz-789"])
        assert result.exit_code == 0


class TestEnvGet:
    def test_get_existing_var(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"environment": ENV_STRING}
        result = runner.invoke(app, ["--json", "env", "get", "comp-xyz-789", "DATABASE_URL"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["key"] == "DATABASE_URL"
        assert data["value"] == "postgres://localhost/mydb"

    def test_get_missing_var_exits_1(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"environment": ENV_STRING}
        result = runner.invoke(app, ["env", "get", "comp-xyz-789", "NONEXISTENT_VAR"])
        assert result.exit_code == 1


class TestEnvSet:
    def test_set_new_variable(self, mock_client: MagicMock, sample_compose: dict) -> None:
        mock_client.get.return_value = sample_compose
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["env", "set", "comp-xyz-789", "NEW_VAR", "new-value"])
        assert result.exit_code == 0

    def test_set_updates_existing_variable(self, mock_client: MagicMock, sample_compose: dict) -> None:
        mock_client.get.return_value = sample_compose
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["env", "set", "comp-xyz-789", "DATABASE_URL", "postgres://new-host/db"])
        assert result.exit_code == 0


class TestEnvDelete:
    def test_delete_existing_var(self, mock_client: MagicMock, sample_compose: dict) -> None:
        mock_client.get.return_value = sample_compose
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["env", "delete", "comp-xyz-789", "DATABASE_URL", "--force"])
        assert result.exit_code == 0

    def test_delete_missing_var_exits_1(self, mock_client: MagicMock, sample_compose: dict) -> None:
        mock_client.get.return_value = sample_compose
        result = runner.invoke(app, ["env", "delete", "comp-xyz-789", "NONEXISTENT_VAR", "--force"])
        assert result.exit_code == 1
