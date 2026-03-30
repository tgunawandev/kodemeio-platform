"""Tests for domains commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()

SAMPLE_DOMAINS = [
    {
        "domainId": "dom-111",
        "host": "web.kodeme.io",
        "port": 3000,
        "https": True,
        "certificateType": "letsencrypt",
    },
    {
        "domainId": "dom-222",
        "host": "api.kodeme.io",
        "port": 8080,
        "https": True,
        "certificateType": "letsencrypt",
    },
]


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestDomainsList:
    def test_list_json_aggregates_from_projects(
        self, mock_client: MagicMock, sample_projects: list[dict], sample_compose: dict
    ) -> None:
        sample_compose_with_domains = dict(sample_compose)

        # The list command calls /project.all, then /compose.one for each compose
        def get_side_effect(endpoint, **kwargs):
            if endpoint == "/project.all":
                return sample_projects
            if endpoint == "/compose.one":
                return sample_compose_with_domains
            if endpoint == "/application.one":
                return {"applicationId": "app-111-222", "name": "frontend", "domains": []}
            return []

        mock_client.get.side_effect = get_side_effect
        result = runner.invoke(app, ["--json", "domains", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_list_no_projects_returns_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "domains", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []


class TestDomainsGet:
    def test_get_domains_for_compose_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_DOMAINS
        result = runner.invoke(app, ["--json", "domains", "get", "comp-xyz-789"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["host"] == "web.kodeme.io"

    def test_get_domains_empty_list(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "domains", "get", "comp-xyz-789"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []


class TestDomainsCreate:
    def test_create_domain_success(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"domainId": "dom-333"}
        result = runner.invoke(
            app,
            ["--json", "domains", "create", "comp-xyz-789", "--host", "new.kodeme.io"],
        )
        assert result.exit_code == 0
        assert "new.kodeme.io" in result.output

    def test_create_domain_with_all_options(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"domainId": "dom-444"}
        result = runner.invoke(
            app,
            [
                "domains",
                "create",
                "comp-xyz-789",
                "--host",
                "app.kodeme.io",
                "--port",
                "3000",
                "--https",
                "--cert",
                "letsencrypt",
                "--service",
                "web",
            ],
        )
        assert result.exit_code == 0


class TestDomainsDelete:
    def test_delete_with_force(self, mock_client: MagicMock) -> None:
        mock_client.delete.return_value = {}
        result = runner.invoke(app, ["domains", "delete", "dom-111", "--force"])
        assert result.exit_code == 0

    def test_delete_prompts_without_force(self, mock_client: MagicMock) -> None:
        mock_client.delete.return_value = {}
        result = runner.invoke(app, ["domains", "delete", "dom-111"], input="y\n")
        assert result.exit_code == 0
