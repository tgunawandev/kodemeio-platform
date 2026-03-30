"""Tests for git commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()

SAMPLE_GIT_PROVIDERS = [
    {
        "gitProviderId": "gp-aaa-111",
        "name": "github-kodemeio",
        "gitProviderType": "github",
        "organizationName": "kodemeio",
        "createdAt": "2026-01-01T00:00:00Z",
    },
    {
        "gitProviderId": "gp-bbb-222",
        "name": "gitlab-self",
        "gitProviderType": "gitlab",
        "organizationName": "internal",
        "createdAt": "2026-02-01T00:00:00Z",
    },
]


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestGitList:
    def test_list_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_GIT_PROVIDERS
        result = runner.invoke(app, ["--json", "git", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "github-kodemeio"

    def test_list_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "git", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []


class TestGitGet:
    def test_get_provider_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_GIT_PROVIDERS[0]
        result = runner.invoke(app, ["--json", "git", "get", "gp-aaa-111"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "github-kodemeio"
        assert data["gitProviderType"] == "github"

    def test_get_not_found_exits_1(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = "not a dict"
        result = runner.invoke(app, ["git", "get", "nonexistent"])
        assert result.exit_code == 1


class TestGitCreate:
    def test_create_github_provider(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"gitProviderId": "gp-new-001"}
        result = runner.invoke(
            app,
            [
                "--json",
                "git",
                "create",
                "--name",
                "my-github",
                "--type",
                "github",
                "--org",
                "myorg",
            ],
        )
        assert result.exit_code == 0
        assert "my-github" in result.output


class TestGitRemove:
    def test_remove_with_force(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["git", "remove", "gp-bbb-222", "--force"])
        assert result.exit_code == 0

    def test_remove_prompts_without_force(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["git", "remove", "gp-bbb-222"], input="y\n")
        assert result.exit_code == 0
