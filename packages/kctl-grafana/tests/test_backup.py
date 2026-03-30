"""Tests for backup commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_grafana.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.org_id = 1
    client.get_version.return_value = "11.4.0"
    return client


class TestBackupCreate:
    def test_backup_create(self, runner: CliRunner, mock_client: MagicMock, tmp_path) -> None:
        output_dir = str(tmp_path / "backup")

        mock_client.get.side_effect = lambda path, **kw: {
            "/search": [{"uid": "dash1", "title": "Overview"}],
            "/dashboards/uid/dash1": {
                "dashboard": {"uid": "dash1", "title": "Overview", "id": 1, "panels": []},
                "meta": {},
            },
            "/datasources": [
                {"uid": "prom1", "name": "Prometheus", "type": "prometheus", "url": "http://prometheus:9090"}
            ],
        }.get(path, [])

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(
                app,
                [
                    "--url",
                    "https://grafana.kodeme.io",
                    "--api-key",
                    "key",
                    "backup",
                    "create",
                    "--output",
                    output_dir,
                ],
            )

        assert result.exit_code == 0
        assert (Path(output_dir) / "manifest.json").exists()
        assert (Path(output_dir) / "dashboards").is_dir()
        assert (Path(output_dir) / "datasources").is_dir()


class TestBackupRestore:
    def test_backup_restore(self, runner: CliRunner, mock_client: MagicMock, tmp_path) -> None:
        # Create a mock backup directory
        backup_dir = tmp_path / "backup"
        (backup_dir / "dashboards").mkdir(parents=True)
        (backup_dir / "datasources").mkdir(parents=True)

        manifest = {"created_at": "20240101-120000", "grafana_version": "11.4.0", "dashboards": 1, "datasources": 1}
        (backup_dir / "manifest.json").write_text(json.dumps(manifest))

        dash_data = {"dashboard": {"uid": "dash1", "title": "Overview", "panels": []}, "overwrite": True}
        (backup_dir / "dashboards" / "overview-dash1.json").write_text(json.dumps(dash_data))

        ds_data = {"uid": "prom1", "name": "Prometheus", "type": "prometheus", "url": "http://prometheus:9090"}
        (backup_dir / "datasources" / "prometheus.json").write_text(json.dumps(ds_data))

        # Datasource does not exist yet
        mock_client.get.side_effect = Exception("Not found")
        mock_client.post.return_value = {"slug": "overview", "uid": "dash1", "url": "/d/dash1"}

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(
                app,
                [
                    "--url",
                    "https://grafana.kodeme.io",
                    "--api-key",
                    "key",
                    "backup",
                    "restore",
                    str(backup_dir),
                ],
            )

        assert result.exit_code == 0

    def test_backup_restore_missing_dir(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(
                app,
                [
                    "--url",
                    "https://grafana.kodeme.io",
                    "--api-key",
                    "key",
                    "backup",
                    "restore",
                    "/nonexistent/path",
                ],
            )

        assert result.exit_code == 1
