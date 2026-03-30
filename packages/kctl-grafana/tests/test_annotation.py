"""Tests for annotation commands."""

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


class TestAnnotationAdd:
    def test_add_annotation(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"id": 42, "message": "Annotation added"}

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
                    "annotation",
                    "add",
                    "Deploy v1.2.3",
                    "--tags",
                    "deploy,production",
                ],
            )

        assert result.exit_code == 0
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[1]["json_body"]["text"] == "Deploy v1.2.3"
        assert call_args[1]["json_body"]["tags"] == ["deploy", "production"]


class TestAnnotationList:
    def test_list_annotations(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {"id": 1, "text": "Deploy v1.2.3", "tags": ["deploy"], "dashboardUID": "global", "created": 1700000000000},
            {"id": 2, "text": "Config change", "tags": ["config"], "dashboardUID": "abc", "created": 1700001000000},
        ]

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(
                app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "annotation", "list"]
            )

        assert result.exit_code == 0
