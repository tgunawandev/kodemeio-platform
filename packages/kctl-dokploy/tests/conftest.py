"""Shared test fixtures for kctl-dokploy tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.core.callbacks import AppContext
from kctl_dokploy.core.client import DokployClient
from kctl_dokploy.core.output import Output


@pytest.fixture
def runner() -> CliRunner:
    """Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    """Mocked DokployClient with predictable responses."""
    client = MagicMock(spec=DokployClient)
    client._root_url = "https://dokploy.test.io"
    client._base_url = "https://dokploy.test.io/api"
    client.check_health.return_value = 200
    client.get.return_value = []
    client.post.return_value = {}
    client.put.return_value = {}
    client.patch.return_value = {}
    client.delete.return_value = {}
    return client


@pytest.fixture
def json_output() -> Output:
    """Output handler in JSON mode for easy assertion."""
    return Output(json_mode=True)


@pytest.fixture
def pretty_output() -> Output:
    """Output handler in pretty mode."""
    return Output(json_mode=False)


@pytest.fixture
def csv_output() -> Output:
    """Output handler in CSV mode."""
    return Output(format="csv")


@pytest.fixture
def yaml_output() -> Output:
    """Output handler in YAML mode."""
    return Output(format="yaml")


@pytest.fixture
def app_context(mock_client: MagicMock) -> AppContext:
    """AppContext with mock client injected."""
    ctx = AppContext(json_mode=True)
    ctx._client = mock_client
    return ctx


# Sample data fixtures


@pytest.fixture
def sample_projects() -> list[dict]:
    return [
        {
            "projectId": "proj-abc-123",
            "name": "kodemeio",
            "description": "Main project",
            "compose": [
                {
                    "composeId": "comp-xyz-789",
                    "name": "web-app",
                    "composeStatus": "done",
                },
                {
                    "composeId": "comp-xyz-456",
                    "name": "api-service",
                    "composeStatus": "running",
                },
            ],
            "applications": [
                {
                    "applicationId": "app-111-222",
                    "name": "frontend",
                    "applicationStatus": "done",
                }
            ],
        },
        {
            "projectId": "proj-def-456",
            "name": "staging",
            "description": "Staging env",
            "compose": [],
            "applications": [],
        },
    ]


@pytest.fixture
def sample_compose() -> dict:
    return {
        "composeId": "comp-xyz-789",
        "name": "web-app",
        "composeStatus": "done",
        "sourceType": "raw",
        "createdAt": "2026-01-15T10:00:00Z",
        "updatedAt": "2026-03-20T14:30:00Z",
        "env": "DATABASE_URL=postgres://localhost/db\nREDIS_URL=redis://localhost",
        "domains": [
            {"host": "web.kodeme.io", "port": 3000},
        ],
    }


@pytest.fixture
def sample_servers() -> list[dict]:
    return [
        {
            "serverId": "srv-001",
            "name": "hetzner-main",
            "ipAddress": "10.0.0.1",
            "serverStatus": "active",
        },
        {
            "serverId": "srv-002",
            "name": "hetzner-worker",
            "ipAddress": "10.0.0.2",
            "serverStatus": "active",
        },
    ]


@pytest.fixture
def mock_config(tmp_path: Path):
    """Redirect kctl-lib config to a temp directory."""
    config_dir = tmp_path / "kodemeio"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text("default_profile: default\nprofiles: {}\n")
    with patch("kctl_lib.config.CONFIG_FILE", config_file):
        yield config_file


@pytest.fixture
def mock_output() -> Output:
    """Output instance in quiet/JSON mode for test assertions."""
    return Output(json_mode=True, quiet=True, format="json")


@pytest.fixture
def mock_context(mock_client: MagicMock, mock_output: Output) -> AppContext:
    """AppContext with mocked client and output."""
    ctx = AppContext(json_mode=True)
    ctx._client = mock_client
    ctx._output = mock_output
    return ctx


@pytest.fixture
def mock_docker_manager() -> MagicMock:
    """Mock DockerManager."""
    from kctl_lib.docker import DockerManager

    return MagicMock(spec=DockerManager)
