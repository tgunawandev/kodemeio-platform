"""Tests for kctl-op vault and projects commands."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_op.cli import app
from kctl_op.core.callbacks import AppContext

runner = CliRunner()


@pytest.fixture()
def _mock_service_config():
    return MagicMock(
        vault="kodemeio-secrets",
        scan_roots=[],
        exclude_patterns=[],
        env_mappings={},
        custom_env_pattern="",
    )


@pytest.fixture(autouse=True)
def _patch_context(mock_context: AppContext, _mock_service_config: MagicMock):
    with (
        patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_context._client),
        patch.object(AppContext, "output", new_callable=PropertyMock, return_value=mock_context._output),
        patch.object(AppContext, "service_config", new_callable=PropertyMock, return_value=_mock_service_config),
    ):
        yield


class TestVaultInfo:
    def test_vault_info_success(self, mock_client: MagicMock) -> None:
        mock_client.vault_info.return_value = {
            "id": "vault-001",
            "name": "kodemeio-secrets",
            "type": "USER_CREATED",
            "items": 42,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        result = runner.invoke(app, ["vault", "info"])
        assert result.exit_code == 0

    def test_vault_info_error(self, mock_client: MagicMock) -> None:
        mock_client.vault_info.side_effect = Exception("not authenticated")
        result = runner.invoke(app, ["vault", "info"])
        assert result.exit_code == 1

    def test_vault_info_help(self) -> None:
        result = runner.invoke(app, ["vault", "info", "--help"])
        assert result.exit_code == 0


class TestVaultItems:
    def test_items_empty(self, mock_client: MagicMock) -> None:
        mock_client.list_items.return_value = []
        result = runner.invoke(app, ["vault", "items"])
        assert result.exit_code == 0

    def test_items_list(self, mock_client: MagicMock) -> None:
        mock_client.list_items.return_value = [
            {
                "id": "item-001",
                "title": "DB Password",
                "category": "PASSWORD",
                "tags": ["db", "prod"],
                "updated_at": "2026-01-01",
                "vault": {"name": "kodemeio-secrets"},
            },
            {
                "id": "item-002",
                "title": "API Key",
                "category": "API_CREDENTIAL",
                "tags": [],
                "updated_at": "2026-02-01",
                "vault": {"name": "kodemeio-secrets"},
            },
        ]
        result = runner.invoke(app, ["vault", "items"])
        assert result.exit_code == 0

    def test_items_error(self, mock_client: MagicMock) -> None:
        mock_client.list_items.side_effect = Exception("vault locked")
        result = runner.invoke(app, ["vault", "items"])
        assert result.exit_code == 1

    def test_vault_create_help(self) -> None:
        result = runner.invoke(app, ["vault", "create", "--help"])
        assert result.exit_code == 0
        assert "--description" in result.output


class TestProjectsList:
    def test_no_projects_found(self, mock_client: MagicMock) -> None:
        mock_client.discover_files.return_value = []
        result = runner.invoke(app, ["projects", "list"])
        assert result.exit_code == 0

    def test_projects_listed(self, mock_client: MagicMock) -> None:
        env_file = MagicMock()
        env_file.project = "myproject"
        env_file.environment = "production"
        env_file.scan_root = "/home/user/projects"
        mock_client.discover_files.return_value = [env_file]
        result = runner.invoke(app, ["projects", "list"])
        assert result.exit_code == 0
        assert "myproject" in result.output

    def test_projects_status_not_found(self, mock_client: MagicMock) -> None:
        mock_client.discover_files.return_value = []
        result = runner.invoke(app, ["projects", "status", "nonexistent"])
        assert result.exit_code == 1

    def test_projects_envs_found(self, mock_client: MagicMock) -> None:
        env_file = MagicMock()
        env_file.project = "myproject"
        env_file.environment = "production"
        env_file.item_title = "myproject/production"
        env_file.path = "/path/to/.env.prod"
        env_file.scan_root = "/home/user/projects"
        mock_client.discover_files.return_value = [env_file]
        result = runner.invoke(app, ["projects", "envs", "myproject"])
        assert result.exit_code == 0

    def test_projects_envs_not_found(self, mock_client: MagicMock) -> None:
        mock_client.discover_files.return_value = []
        result = runner.invoke(app, ["projects", "envs", "ghost"])
        assert result.exit_code == 1
