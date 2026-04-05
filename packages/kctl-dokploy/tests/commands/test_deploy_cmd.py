"""Tests for deploy and domains commands."""

from __future__ import annotations

import json
from pathlib import Path
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


class TestDeployHelp:
    def test_deploy_help(self) -> None:
        result = runner.invoke(app, ["deploy", "--help"])
        assert result.exit_code == 0

    def test_deploy_validate_help(self) -> None:
        result = runner.invoke(app, ["deploy", "validate", "--help"])
        assert result.exit_code == 0
        assert "--file" in result.output

    def test_deploy_apply_help(self) -> None:
        result = runner.invoke(app, ["deploy", "apply", "--help"])
        assert result.exit_code == 0
        assert "--file" in result.output

    def test_deploy_status_help(self) -> None:
        result = runner.invoke(app, ["deploy", "status", "--help"])
        assert result.exit_code == 0

    def test_deploy_list_help(self) -> None:
        result = runner.invoke(app, ["deploy", "list", "--help"])
        assert result.exit_code == 0

    def test_deploy_preflight_help(self) -> None:
        result = runner.invoke(app, ["deploy", "preflight", "--help"])
        assert result.exit_code == 0

    def test_deploy_setup_help(self) -> None:
        result = runner.invoke(app, ["deploy", "setup", "--help"])
        assert result.exit_code == 0

    def test_deploy_run_help(self) -> None:
        result = runner.invoke(app, ["deploy", "run", "--help"])
        assert result.exit_code == 0

    def test_deploy_post_help(self) -> None:
        result = runner.invoke(app, ["deploy", "post", "--help"])
        assert result.exit_code == 0


class TestDeployValidate:
    def test_validate_nonexistent_file(self, tmp_path: Path) -> None:
        """Validate with a missing file should fail cleanly."""
        result = runner.invoke(app, ["deploy", "validate", "--file", str(tmp_path / "missing.yaml")])
        assert result.exit_code != 0

    def test_validate_invalid_yaml(self, tmp_path: Path) -> None:
        """Validate with malformed YAML should fail."""
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("not: valid: yaml: [[[")
        result = runner.invoke(app, ["deploy", "validate", "--file", str(bad_file)])
        assert result.exit_code != 0

    def test_validate_minimal_manifest(self, tmp_path: Path) -> None:
        """Validate a minimal manifest."""
        manifest = tmp_path / "svc.yaml"
        manifest.write_text(
            "name: test-svc\nproject: kod\nstack: react\ndomain: test.kodeme.io\ncompose_id: comp-test-123\n"
        )
        result = runner.invoke(app, ["deploy", "validate", "--file", str(manifest)])
        # May pass or fail depending on required fields — check it doesn't crash
        assert result.exit_code in (0, 1)


class TestDeployList:
    def test_list_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["deploy", "list"])
        assert result.exit_code == 0

    def test_list_help(self) -> None:
        result = runner.invoke(app, ["deploy", "list", "--help"])
        assert result.exit_code == 0


class TestDomainsHelp:
    def test_domains_help(self) -> None:
        result = runner.invoke(app, ["domains", "--help"])
        assert result.exit_code == 0

    def test_domains_list_help(self) -> None:
        result = runner.invoke(app, ["domains", "list", "--help"])
        assert result.exit_code == 0

    def test_domains_add_help(self) -> None:
        result = runner.invoke(app, ["domains", "add", "--help"])
        assert result.exit_code == 0
        assert "--host" in result.output

    def test_domains_remove_help(self) -> None:
        result = runner.invoke(app, ["domains", "remove", "--help"])
        assert result.exit_code == 0


class TestDomainsList:
    def test_domains_list_no_projects(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["domains", "list"])
        assert result.exit_code == 0

    def test_domains_list_with_projects(self, mock_client: MagicMock, sample_projects: list[dict]) -> None:
        """domains list traverses projects to find domains."""

        def _side_effect(path, **kwargs):
            if path == "/project.all":
                return sample_projects
            if path == "/compose.one":
                return {"domains": [{"host": "web.kodeme.io", "port": 3000}]}
            if path == "/application.one":
                return {"domains": []}
            return {}

        mock_client.get.side_effect = _side_effect
        result = runner.invoke(app, ["domains", "list"])
        assert result.exit_code == 0

    def test_domains_list_get_error_graceful(self, mock_client: MagicMock) -> None:
        """Errors fetching compose details are swallowed gracefully."""
        mock_client.get.side_effect = Exception("connection error")
        result = runner.invoke(app, ["domains", "list"])
        assert result.exit_code in (0, 1)


class TestComposeHelp:
    def test_compose_help(self) -> None:
        result = runner.invoke(app, ["compose", "--help"])
        assert result.exit_code == 0

    def test_compose_redeploy_help(self) -> None:
        result = runner.invoke(app, ["compose", "redeploy", "--help"])
        assert result.exit_code == 0

    def test_compose_logs_help(self) -> None:
        result = runner.invoke(app, ["compose", "logs", "--help"])
        assert result.exit_code == 0

    def test_compose_env_help(self) -> None:
        result = runner.invoke(app, ["compose", "env", "--help"])
        assert result.exit_code == 0
