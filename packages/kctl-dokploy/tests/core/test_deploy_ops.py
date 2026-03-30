"""Tests for atomic deployment orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kctl_dokploy.core.deploy_ops import (
    DeploymentState,
    DeployStep,
    backup_compose_state,
    deploy_atomic,
    rollback_on_failure,
)
from kctl_dokploy.core.output import Output


@pytest.fixture
def mock_output() -> MagicMock:
    return MagicMock(spec=Output)


class TestDeploymentState:
    def test_defaults(self) -> None:
        state = DeploymentState()
        assert state.compose_id == ""
        assert state.is_new is False
        assert state.step is None


class TestBackupComposeState:
    def test_captures_snapshot(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"composeId": "c1", "composeFile": "version: '3'", "env": "KEY=val"}
        result = backup_compose_state(mock_client, "c1")
        assert result is not None
        assert result["composeId"] == "c1"

    def test_returns_none_on_error(self, mock_client: MagicMock) -> None:
        mock_client.get.side_effect = Exception("API down")
        result = backup_compose_state(mock_client, "c1")
        assert result is None


class TestRollbackOnFailure:
    def test_rollback_new_compose(self, mock_client: MagicMock, mock_output: MagicMock) -> None:
        state = DeploymentState(compose_id="c1", step=DeployStep.COMPOSE_UPSERT, is_new=True)
        result = rollback_on_failure(mock_client, state, mock_output)
        assert result is True
        mock_client.post.assert_called_once()

    def test_rollback_deploy_with_snapshot(self, mock_client: MagicMock, mock_output: MagicMock) -> None:
        state = DeploymentState(
            compose_id="c1",
            step=DeployStep.DEPLOY,
            previous_snapshot={"composeFile": "old", "env": "OLD=val"},
        )
        result = rollback_on_failure(mock_client, state, mock_output)
        assert result is True
        # Should restore compose + redeploy
        assert mock_client.post.call_count >= 2

    def test_rollback_domain(self, mock_client: MagicMock, mock_output: MagicMock) -> None:
        state = DeploymentState(compose_id="c1", domain_id="d1", step=DeployStep.DOMAIN_CONFIG)
        result = rollback_on_failure(mock_client, state, mock_output)
        assert result is True

    def test_empty_state_noop(self, mock_client: MagicMock, mock_output: MagicMock) -> None:
        state = DeploymentState()
        result = rollback_on_failure(mock_client, state, mock_output)
        assert result is True


class TestDeployAtomic:
    def test_successful_deploy(self, mock_client: MagicMock, mock_output: MagicMock, tmp_path: Path) -> None:
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3'\nservices:\n  web:\n    image: nginx")

        mock_client.get.return_value = [{"projectId": "p1", "name": "test", "compose": []}]
        mock_client.post.return_value = {"composeId": "new-id"}

        result = deploy_atomic(
            mock_client,
            mock_output,
            name="test-app",
            project_id="p1",
            compose_file=compose_file,
            skip_health=True,
        )
        assert result.success is True
        assert result.compose_id == "new-id"
        assert len(result.steps_completed) >= 4

    def test_missing_compose_file(self, mock_client: MagicMock, mock_output: MagicMock) -> None:
        mock_client.get.return_value = [{"projectId": "p1", "name": "test", "compose": []}]
        mock_client.post.return_value = {"composeId": "new-id"}

        result = deploy_atomic(
            mock_client,
            mock_output,
            name="test-app",
            project_id="p1",
            compose_file="/nonexistent/file.yml",
            skip_health=True,
        )
        assert result.success is False
        assert "not found" in result.error

    def test_finds_existing_compose(self, mock_client: MagicMock, mock_output: MagicMock, tmp_path: Path) -> None:
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3'")

        mock_client.get.return_value = [
            {
                "projectId": "p1",
                "name": "test",
                "compose": [{"composeId": "existing-id", "name": "test-app"}],
            }
        ]
        mock_client.post.return_value = {}

        result = deploy_atomic(
            mock_client,
            mock_output,
            name="test-app",
            project_id="p1",
            compose_file=compose_file,
            skip_health=True,
        )
        assert result.success is True
        assert result.compose_id == "existing-id"

    def test_with_env_file(self, mock_client: MagicMock, mock_output: MagicMock, tmp_path: Path) -> None:
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3'")
        env_file = tmp_path / ".env"
        env_file.write_text("DB_HOST=localhost\nDB_PORT=5432")

        mock_client.get.return_value = [{"projectId": "p1", "name": "test", "compose": []}]
        mock_client.post.return_value = {"composeId": "new-id"}

        result = deploy_atomic(
            mock_client,
            mock_output,
            name="test-app",
            project_id="p1",
            compose_file=compose_file,
            env_file=env_file,
            skip_health=True,
        )
        assert result.success is True
        assert "env_update" in result.steps_completed

    def test_rollback_on_failure(self, mock_client: MagicMock, mock_output: MagicMock, tmp_path: Path) -> None:
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3'")

        mock_client.get.return_value = [{"projectId": "p1", "name": "test", "compose": []}]
        # First post creates, second post (update) fails
        mock_client.post.side_effect = [
            {"composeId": "new-id"},  # create
            Exception("Update failed"),  # file upload fails
        ]

        result = deploy_atomic(
            mock_client,
            mock_output,
            name="test-app",
            project_id="p1",
            compose_file=compose_file,
            skip_health=True,
            rollback_on_fail=True,
        )
        assert result.success is False
        assert result.rolled_back is True
