"""Tests for setup commands."""

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
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") or stripped.startswith("{"):
            return "\n".join(lines[i:])
    return output


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


def _setup_full_mock(mock_client: MagicMock) -> None:
    """Configure mock_client for setup check — all APIs respond successfully."""

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
        if endpoint == "/server.all":
            return [{"serverId": "s-1", "name": "main"}]
        if endpoint == "/docker.getContainers":
            return [{"containerId": "c1", "name": "web_1"}]
        if endpoint == "/certificate.all":
            return [{"certificateId": "cert-1", "name": "wildcard"}]
        if endpoint == "/user.all":
            return [{"userId": "u-1", "email": "admin@kodeme.io"}]
        if endpoint == "/destination.all":
            return [{"destinationId": "dst-1", "name": "s3"}]
        if endpoint == "/backup.all":
            return [{"backupId": "b-1", "enabled": True}]
        if endpoint == "/notification.all":
            return [{"notificationId": "n-1", "name": "slack"}]
        if endpoint == "/gitProvider.all":
            return [{"gitProviderId": "gp-1", "name": "github"}]
        if endpoint == "/compose.one":
            return {"composeId": "c-1", "name": "web", "domains": [{"host": "web.kodeme.io"}]}
        if endpoint == "/application.one":
            return {"applicationId": "a-1", "name": "app", "domains": []}
        return []

    mock_client.get.side_effect = get_side_effect


class TestSetupCheck:
    def test_check_json_returns_list_of_checks(self, mock_client: MagicMock) -> None:
        _setup_full_mock(mock_client)
        with patch(
            "kctl_dokploy.commands.setup.resolve_active_profile_name",
            return_value="default",
        ):
            result = runner.invoke(app, ["--json", "setup", "check"])
        assert result.exit_code == 0
        data = json.loads(_extract_json(result.output))
        assert isinstance(data, list)
        assert len(data) > 0

    def test_check_json_check_structure(self, mock_client: MagicMock) -> None:
        _setup_full_mock(mock_client)
        with patch(
            "kctl_dokploy.commands.setup.resolve_active_profile_name",
            return_value="default",
        ):
            result = runner.invoke(app, ["--json", "setup", "check"])
        assert result.exit_code == 0
        data = json.loads(_extract_json(result.output))
        # Each check should have name, category, status, message
        for check in data:
            assert "name" in check
            assert "category" in check
            assert "status" in check
            assert "message" in check

    def test_check_api_connectivity_pass(self, mock_client: MagicMock) -> None:
        _setup_full_mock(mock_client)
        with patch(
            "kctl_dokploy.commands.setup.resolve_active_profile_name",
            return_value="default",
        ):
            result = runner.invoke(app, ["--json", "setup", "check"])
        assert result.exit_code == 0
        data = json.loads(_extract_json(result.output))
        connectivity_checks = [c for c in data if c["name"] == "API connectivity"]
        assert len(connectivity_checks) == 1
        assert connectivity_checks[0]["status"] == "pass"

    def test_check_with_error_service_reports_fail_check(self, mock_client: MagicMock) -> None:
        """In JSON mode, setup check always exits 0 but reports fail status in check items."""

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
            return []

        mock_client.get.side_effect = get_side_effect
        with patch(
            "kctl_dokploy.commands.setup.resolve_active_profile_name",
            return_value="default",
        ):
            result = runner.invoke(app, ["--json", "setup", "check"])
        # In JSON mode, setup outputs JSON and returns 0 (Exit(1) is after pretty table)
        assert result.exit_code == 0
        data = json.loads(_extract_json(result.output))
        failed_checks = [c for c in data if c["status"] == "fail"]
        assert len(failed_checks) > 0

    def test_check_pretty_exits_1_with_failed_checks(self, mock_client: MagicMock) -> None:
        """In pretty mode, setup check exits 1 when there are fail-status checks."""

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
            return []

        mock_client.get.side_effect = get_side_effect
        with patch(
            "kctl_dokploy.commands.setup.resolve_active_profile_name",
            return_value="default",
        ):
            result = runner.invoke(app, ["setup", "check"])
        assert result.exit_code == 1
