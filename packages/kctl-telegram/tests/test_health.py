"""Tests for health check commands."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_telegram.cli import app
from kctl_telegram.core.callbacks import AppContext
from kctl_telegram.core.client import TelegramClient


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock(spec=TelegramClient)
    client.base_url = "https://telegram.kodeme.io"
    return client


class TestHealthCommand:
    def test_healthy_full_score(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """All probes pass → score=100, exit 0."""
        mock_client.check_health.return_value = {"status": "healthy", "version": "1.2.3"}
        mock_client.check_ready.return_value = {"status": "ready"}
        mock_client.get.side_effect = [
            {"results": [{"id": 1}], "pagination": {"count": 1, "next": None}},
            {"results": [{"id": 1}], "pagination": {"count": 1, "next": None}},
        ]
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["health"])
        assert result.exit_code == 0

    def test_healthy_ok_status_variant(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """Status 'ok' is also accepted as healthy."""
        mock_client.check_health.return_value = {"status": "ok", "version": "2.0.0"}
        mock_client.check_ready.return_value = {"status": "ok"}
        mock_client.get.side_effect = [
            {"results": [{"id": 1}], "pagination": {"count": 2}},
            {"results": [{"id": 1}], "pagination": {"count": 3}},
        ]
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["health"])
        assert result.exit_code == 0

    def test_unhealthy_exits_1(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """All probes fail → score < 50, exit code 1."""
        mock_client.check_health.side_effect = Exception("Connection refused")
        mock_client.check_ready.side_effect = Exception("Connection refused")
        mock_client.get.side_effect = Exception("Connection refused")
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["health"])
        assert result.exit_code == 1

    def test_partial_health_high_score_exits_0(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """health + ready pass (60pts) → exits 0."""
        mock_client.check_health.return_value = {"status": "healthy", "version": "1.0.0"}
        mock_client.check_ready.return_value = {"status": "ready"}
        mock_client.get.side_effect = Exception("no bots/groups")
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["health"])
        assert result.exit_code == 0

    def test_partial_health_low_score_exits_1(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """Only bots exist (20pts) → score < 50, exits 1."""
        mock_client.check_health.side_effect = Exception("down")
        mock_client.check_ready.side_effect = Exception("down")
        mock_client.get.side_effect = [
            {"results": [{"id": 1}], "pagination": {"count": 1}},
            Exception("no groups"),
        ]
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["health"])
        assert result.exit_code == 1

    def test_health_with_no_bots_or_groups(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """health+ready pass, but zero bots and groups (60pts) → exits 0."""
        mock_client.check_health.return_value = {"status": "healthy", "version": "1.0.0"}
        mock_client.check_ready.return_value = {"status": "ready"}
        mock_client.get.side_effect = [
            {"results": [], "pagination": {"count": 0}},
            {"results": [], "pagination": {"count": 0}},
        ]
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["health"])
        assert result.exit_code == 0

    def test_health_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.check_health.return_value = {"status": "healthy", "version": "1.0.0"}
        mock_client.check_ready.return_value = {"status": "ready"}
        mock_client.get.side_effect = [
            {"results": [{"id": 1}], "pagination": {"count": 1}},
            {"results": [{"id": 1}], "pagination": {"count": 1}},
        ]
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["--json", "health"])
        assert result.exit_code == 0

    def test_health_unhealthy_status(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """Status not in ('healthy','ok') counts as unhealthy probe."""
        mock_client.check_health.return_value = {"status": "degraded", "version": "1.0.0"}
        mock_client.check_ready.return_value = {"status": "not_ready"}
        mock_client.get.side_effect = [
            {"results": [], "pagination": {"count": 0}},
            {"results": [], "pagination": {"count": 0}},
        ]
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["health"])
        assert result.exit_code == 1

    def test_health_count_from_results_length(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """Falls back to len(results) when pagination.count is absent."""
        mock_client.check_health.return_value = {"status": "healthy", "version": "1.0.0"}
        mock_client.check_ready.return_value = {"status": "ready"}
        mock_client.get.side_effect = [
            {"results": [{"id": 1}, {"id": 2}]},
            {"results": [{"id": 10}]},
        ]
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["health"])
        assert result.exit_code == 0

    def test_health_no_version_in_response(self, runner: CliRunner, mock_client: MagicMock) -> None:
        """Missing version field shows 'unknown'."""
        mock_client.check_health.return_value = {"status": "healthy"}
        mock_client.check_ready.return_value = {"status": "ready"}
        mock_client.get.side_effect = [
            {"results": [], "pagination": {"count": 0}},
            {"results": [], "pagination": {"count": 0}},
        ]
        with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
            result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
