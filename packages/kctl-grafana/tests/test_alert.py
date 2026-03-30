"""Tests for alert commands."""

from __future__ import annotations

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
    return client


class TestAlertList:
    def test_list_alerts(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {
                "uid": "rule1",
                "title": "High CPU",
                "folderUID": "infra",
                "ruleGroup": "cpu",
                "for": "5m",
                "labels": {"severity": "critical"},
            },
            {
                "uid": "rule2",
                "title": "Low Disk",
                "folderUID": "infra",
                "ruleGroup": "disk",
                "for": "10m",
                "labels": {"severity": "warning"},
            },
        ]

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "alert", "list"])

        assert result.exit_code == 0


class TestAlertShow:
    def test_show_alert(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "uid": "rule1",
            "title": "High CPU",
            "folderUID": "infra",
            "ruleGroup": "cpu",
            "for": "5m",
            "condition": "B",
            "noDataState": "NoData",
            "execErrState": "Error",
            "updated": "2024-01-01T00:00:00Z",
            "provenance": "",
            "labels": {"severity": "critical"},
            "annotations": {"summary": "CPU usage above 90%"},
        }

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(
                app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "alert", "show", "rule1"]
            )

        assert result.exit_code == 0


class TestAlertSilence:
    def test_silence_alert(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"uid": "rule1", "title": "High CPU"}
        mock_client.post.return_value = {"silenceID": "silence-abc"}

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
                    "alert",
                    "silence",
                    "rule1",
                    "--duration",
                    "2h",
                ],
            )

        assert result.exit_code == 0
        mock_client.post.assert_called_once()


class TestAlertContacts:
    def test_list_contacts(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {"uid": "cp1", "name": "Telegram", "type": "telegram", "provenance": "file"},
            {"uid": "cp2", "name": "Email", "type": "email", "provenance": ""},
        ]

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "alert", "contacts"])

        assert result.exit_code == 0
