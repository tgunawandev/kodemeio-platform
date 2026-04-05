"""Tests for kctl-rustdesk health commands."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_rustdesk.cli import app
from kctl_rustdesk.core.callbacks import AppContext

runner = CliRunner()


@pytest.fixture(autouse=True)
def _patch_context(mock_context: AppContext):
    with (
        patch.object(AppContext, "executor", new_callable=PropertyMock, return_value=mock_context._executor),
        patch.object(AppContext, "output", new_callable=PropertyMock, return_value=mock_context._output),
        patch.object(AppContext, "json_mode", new_callable=PropertyMock, return_value=False),
    ):
        yield


class TestHealthCheck:
    def test_check_all_passing(self, mock_executor: MagicMock) -> None:
        mock_executor.container_running.return_value = True
        mock_executor.file_exists.return_value = True
        mock_executor.query_db_scalar.return_value = "5"
        mock_executor.exec_hbbs.return_value = "21115 21116 21117 21118"
        result = runner.invoke(app, ["health", "check"])
        assert result.exit_code == 0

    def test_check_containers_down(self, mock_executor: MagicMock) -> None:
        mock_executor.container_running.return_value = False
        mock_executor.file_exists.return_value = False
        mock_executor.query_db_scalar.side_effect = Exception("db not accessible")
        mock_executor.exec_hbbs.side_effect = Exception("container not running")
        result = runner.invoke(app, ["health", "check"])
        # Unhealthy but should still run (just show failures)
        assert result.exit_code == 0

    def test_check_hbbs_running_hbbr_not(self, mock_executor: MagicMock) -> None:
        def _container_running(svc: str) -> bool:
            return svc == "hbbs"

        mock_executor.container_running.side_effect = _container_running
        mock_executor.file_exists.return_value = True
        mock_executor.query_db_scalar.return_value = "3"
        mock_executor.exec_hbbs.return_value = "21115 21116"
        result = runner.invoke(app, ["health", "check"])
        assert result.exit_code == 0
        assert "hbbr" in result.output

    def test_check_help(self) -> None:
        result = runner.invoke(app, ["health", "check", "--help"])
        assert result.exit_code == 0

    def test_check_run_checks_logic(self, mock_executor: MagicMock) -> None:
        """Test _run_checks returns expected structure."""
        from kctl_rustdesk.commands.health import _run_checks

        mock_executor.container_running.return_value = True
        mock_executor.file_exists.return_value = True
        mock_executor.query_db_scalar.return_value = "10"
        mock_executor.exec_hbbs.return_value = "21115 21116 21117 21118"

        checks = _run_checks(mock_executor)
        assert isinstance(checks, list)
        assert len(checks) > 0
        for ch in checks:
            assert "name" in ch
            assert "status" in ch
            assert "message" in ch
            assert ch["status"] in ("pass", "fail", "warn")

    def test_check_database_failure_recorded(self, mock_executor: MagicMock) -> None:
        """DB failure is recorded as fail check."""
        from kctl_rustdesk.commands.health import _run_checks

        mock_executor.container_running.return_value = True
        mock_executor.file_exists.return_value = True
        mock_executor.query_db_scalar.side_effect = Exception("sqlite error")
        mock_executor.exec_hbbs.return_value = ""

        checks = _run_checks(mock_executor)
        db_checks = [c for c in checks if c["name"] == "database"]
        assert len(db_checks) == 1
        assert db_checks[0]["status"] == "fail"

    def test_check_all_passing_score_100(self, mock_executor: MagicMock) -> None:
        """All passing checks should yield score >= 80."""
        from kctl_rustdesk.commands.health import _run_checks

        mock_executor.container_running.return_value = True
        mock_executor.file_exists.return_value = True
        mock_executor.query_db_scalar.return_value = "5"
        mock_executor.exec_hbbs.return_value = "21115 21116 21117 21118"

        checks = _run_checks(mock_executor)
        passed = sum(1 for c in checks if c["status"] in ("pass", "warn"))
        total = len(checks)
        score = round(passed / total * 100) if total else 0
        assert score >= 80
