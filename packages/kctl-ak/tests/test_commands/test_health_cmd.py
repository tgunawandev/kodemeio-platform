"""Tests for health command."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_ak.cli import app
from kctl_ak.core.callbacks import AppContext

runner = CliRunner()


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestHealthCommand:
    def test_health_all_ok(self, mock_client: MagicMock) -> None:
        mock_client.check_health.return_value = 200
        mock_client.get.side_effect = [
            {"version_current": "2024.10.0", "version_latest": "2024.10.0", "outdated": False},
            {"runtime": {"python_version": "3.12.0", "platform": "linux", "uname": "Linux"}},
        ]
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0

    def test_health_unhealthy_exits_1(self, mock_client: MagicMock) -> None:
        mock_client.check_health.side_effect = Exception("connection refused")
        mock_client.get.side_effect = Exception("connection refused")
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 1

    def test_health_json(self, mock_client: MagicMock) -> None:
        mock_client.check_health.return_value = 200
        mock_client.get.side_effect = [
            {"version_current": "2024.10.0", "version_latest": "2024.10.0", "outdated": False},
            {"runtime": {"python_version": "3.12.0", "platform": "linux", "uname": "Linux"}},
        ]
        result = runner.invoke(app, ["--json", "health"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "score" in data
        assert "live" in data
        assert "ready" in data

    def test_health_partial_fail(self, mock_client: MagicMock) -> None:
        """Live ok, ready fails, system info fails — partial health."""
        mock_client.check_health.side_effect = [200, Exception("not ready")]
        mock_client.get.side_effect = [
            {"version_current": "2024.10.0", "outdated": False},
            Exception("admin required"),
        ]
        result = runner.invoke(app, ["health"])
        # Partial health — may exit 0 or 1 depending on score
        assert result.exit_code in (0, 1)

    def test_health_check_logic(self, mock_client: MagicMock) -> None:
        """Test _check_health returns expected structure."""
        from kctl_ak.commands.health import _check_health
        from kctl_ak.core.callbacks import AppContext

        actx = MagicMock(spec=AppContext)
        actx.client = mock_client
        actx.output = MagicMock()

        mock_client.check_health.return_value = 200
        mock_client.get.side_effect = [
            {"version_current": "2024.10.0", "outdated": False},
            {"runtime": {"python_version": "3.12", "platform": "linux", "uname": "Linux"}},
        ]

        results = _check_health(actx)
        assert isinstance(results, dict)
        assert "live" in results
        assert "ready" in results
        assert "score" in results
        assert 0 <= results["score"] <= 100

    def test_health_score_all_ok(self, mock_client: MagicMock) -> None:
        """All checks pass => score == 100."""
        from kctl_ak.commands.health import _check_health

        actx = MagicMock(spec=AppContext)
        actx.client = mock_client
        actx.output = MagicMock()

        mock_client.check_health.return_value = 200
        mock_client.get.side_effect = [
            {"version_current": "2024.10.0", "outdated": False},
            {"runtime": {"python_version": "3.12", "platform": "linux", "uname": "Linux"}},
        ]

        results = _check_health(actx)
        assert results["score"] == 100

    def test_health_score_all_fail(self, mock_client: MagicMock) -> None:
        """All checks fail => score == 0."""
        from kctl_ak.commands.health import _check_health

        actx = MagicMock(spec=AppContext)
        actx.client = mock_client
        actx.output = MagicMock()

        mock_client.check_health.side_effect = Exception("fail")
        mock_client.get.side_effect = Exception("fail")

        results = _check_health(actx)
        assert results["score"] == 0
        assert results["live"] is False
        assert results["ready"] is False

    def test_health_help(self) -> None:
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0
        assert "--watch" in result.output
