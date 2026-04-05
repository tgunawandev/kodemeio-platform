"""Tests for flows command group."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_ak.cli import app
from kctl_ak.core.callbacks import AppContext

runner = CliRunner()


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


SAMPLE_FLOWS = [
    {
        "pk": "flow-001",
        "slug": "default-authentication-flow",
        "name": "Default Authentication",
        "designation": "authentication",
        "title": "Login",
        "policy_engine_mode": "all",
        "compatibility_mode": False,
        "denied_action": "message_continue",
        "layout": "stacked",
        "authentication": "none",
        "background": "",
    },
    {
        "pk": "flow-002",
        "slug": "default-authorization-flow",
        "name": "Default Authorization",
        "designation": "authorization",
        "title": "Authorize",
        "policy_engine_mode": "all",
        "compatibility_mode": False,
        "denied_action": "message",
        "layout": "stacked",
        "authentication": "none",
        "background": "",
    },
]


class TestFlowsList:
    def test_list_flows(self, mock_client: MagicMock) -> None:
        mock_client.get_all.return_value = SAMPLE_FLOWS
        result = runner.invoke(app, ["flows", "list"])
        assert result.exit_code == 0
        assert "default-authentication-flow" in result.output

    def test_list_flows_json(self, mock_client: MagicMock) -> None:
        mock_client.get_all.return_value = SAMPLE_FLOWS
        result = runner.invoke(app, ["--json", "flows", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_list_flows_empty(self, mock_client: MagicMock) -> None:
        mock_client.get_all.return_value = []
        result = runner.invoke(app, ["flows", "list"])
        assert result.exit_code == 0

    def test_list_with_designation_filter(self, mock_client: MagicMock) -> None:
        mock_client.get_all.return_value = [SAMPLE_FLOWS[0]]
        result = runner.invoke(app, ["flows", "list", "--designation", "authentication"])
        assert result.exit_code == 0
        # Verify designation was passed as param
        call_kwargs = mock_client.get_all.call_args
        assert "params" in call_kwargs.kwargs
        assert call_kwargs.kwargs["params"].get("designation") == "authentication"

    def test_list_help(self) -> None:
        result = runner.invoke(app, ["flows", "list", "--help"])
        assert result.exit_code == 0
        assert "--designation" in result.output


class TestFlowsGet:
    def test_get_flow(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_FLOWS[0]
        result = runner.invoke(app, ["flows", "get", "default-authentication-flow"])
        assert result.exit_code == 0
        assert "authentication" in result.output

    def test_get_flow_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_FLOWS[0]
        result = runner.invoke(app, ["--json", "flows", "get", "default-authentication-flow"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["slug"] == "default-authentication-flow"

    def test_get_help(self) -> None:
        result = runner.invoke(app, ["flows", "get", "--help"])
        assert result.exit_code == 0


class TestFlowsBindings:
    def test_bindings(self, mock_client: MagicMock) -> None:
        mock_client.get_all.return_value = [
            {
                "order": 10,
                "stage_obj": {
                    "name": "default-authentication-identification",
                    "verbose_name": "Identification Stage",
                    "component": "ak-stage-identification",
                    "pk": "stage-001",
                },
                "evaluate_on_plan": True,
                "re_evaluate_policies": False,
                "invalid_response_action": "retry",
            }
        ]
        result = runner.invoke(app, ["flows", "bindings", "default-authentication-flow"])
        assert result.exit_code == 0

    def test_bindings_empty(self, mock_client: MagicMock) -> None:
        mock_client.get_all.return_value = []
        result = runner.invoke(app, ["flows", "bindings", "some-flow"])
        assert result.exit_code == 0

    def test_bindings_help(self) -> None:
        result = runner.invoke(app, ["flows", "bindings", "--help"])
        assert result.exit_code == 0


class TestFlowsStages:
    def test_stages(self, mock_client: MagicMock) -> None:
        mock_client.get_all.return_value = [
            {
                "order": 10,
                "stage_obj": {
                    "pk": "stage-001",
                    "name": "id-stage",
                    "verbose_name": "Identification",
                    "component": "ak-stage-identification",
                },
            }
        ]
        result = runner.invoke(app, ["flows", "stages", "default-authentication-flow"])
        assert result.exit_code == 0
        assert "id-stage" in result.output

    def test_stages_help(self) -> None:
        result = runner.invoke(app, ["flows", "stages", "--help"])
        assert result.exit_code == 0


class TestFlowsExecute:
    def test_execute_shows_url(self, mock_client: MagicMock) -> None:
        mock_client._root_url = "https://auth.kodeme.io"
        result = runner.invoke(app, ["flows", "execute", "default-authentication-flow"])
        assert result.exit_code == 0
        assert "default-authentication-flow" in result.output

    def test_execute_json(self, mock_client: MagicMock) -> None:
        mock_client._root_url = "https://auth.kodeme.io"
        result = runner.invoke(app, ["--json", "flows", "execute", "default-authentication-flow"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "execute_url" in data
        assert "default-authentication-flow" in data["execute_url"]

    def test_execute_help(self) -> None:
        result = runner.invoke(app, ["flows", "execute", "--help"])
        assert result.exit_code == 0
