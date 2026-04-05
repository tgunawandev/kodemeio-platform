"""Tests for kctl-rustdesk peers commands."""

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
    ):
        yield


class TestPeersList:
    def test_list_all_peers(self, mock_executor: MagicMock) -> None:
        mock_executor.query_db.return_value = [
            {"id": "123456", "uuid": "abc-def", "last_online": "2026-04-01 12:00:00", "note": "dev laptop"},
            {"id": "789012", "uuid": "ghi-jkl", "last_online": "2026-04-02 09:00:00", "note": ""},
        ]
        result = runner.invoke(app, ["peers", "list"])
        assert result.exit_code == 0
        assert "123456" in result.output

    def test_list_empty(self, mock_executor: MagicMock) -> None:
        mock_executor.query_db.return_value = []
        result = runner.invoke(app, ["peers", "list"])
        assert result.exit_code == 0

    def test_list_online_flag(self, mock_executor: MagicMock) -> None:
        mock_executor.query_db.return_value = [
            {"id": "111", "uuid": "xxx", "last_online": "2026-04-05 10:00:00", "note": ""},
        ]
        result = runner.invoke(app, ["peers", "list", "--online"])
        assert result.exit_code == 0
        # Verify it queried with the online filter SQL
        call_args = mock_executor.query_db.call_args[0][0]
        assert "last_online" in call_args

    def test_list_help(self) -> None:
        result = runner.invoke(app, ["peers", "list", "--help"])
        assert result.exit_code == 0
        assert "--online" in result.output


class TestPeersGet:
    def test_get_existing_peer(self, mock_executor: MagicMock) -> None:
        mock_executor.query_db.return_value = [
            {
                "id": "123456",
                "uuid": "abc-def",
                "pk": "pubkey",
                "created_at": "2026-01-01",
                "last_online": "2026-04-01",
                "note": "dev",
            }
        ]
        result = runner.invoke(app, ["peers", "get", "123456"])
        assert result.exit_code == 0
        assert "123456" in result.output

    def test_get_not_found(self, mock_executor: MagicMock) -> None:
        mock_executor.query_db.return_value = []
        result = runner.invoke(app, ["peers", "get", "nonexistent"])
        assert result.exit_code == 1

    def test_get_help(self) -> None:
        result = runner.invoke(app, ["peers", "get", "--help"])
        assert result.exit_code == 0


class TestPeersCount:
    def test_count_returns_values(self, mock_executor: MagicMock) -> None:
        mock_executor.query_db_scalar.side_effect = ["25", "3"]
        result = runner.invoke(app, ["peers", "count"])
        assert result.exit_code == 0

    def test_count_help(self) -> None:
        result = runner.invoke(app, ["peers", "count", "--help"])
        assert result.exit_code == 0


class TestPeersSearch:
    def test_search_with_results(self, mock_executor: MagicMock) -> None:
        mock_executor.query_db.return_value = [
            {"id": "abc123", "uuid": "xxx", "last_online": "2026-04-01", "note": "server"}
        ]
        result = runner.invoke(app, ["peers", "search", "abc"])
        assert result.exit_code == 0
        assert "abc123" in result.output

    def test_search_no_results(self, mock_executor: MagicMock) -> None:
        mock_executor.query_db.return_value = []
        result = runner.invoke(app, ["peers", "search", "zzz"])
        assert result.exit_code == 0

    def test_search_help(self) -> None:
        result = runner.invoke(app, ["peers", "search", "--help"])
        assert result.exit_code == 0


class TestPeersExport:
    def test_export_peers(self, mock_executor: MagicMock) -> None:
        mock_executor.query_db.return_value = [
            {"id": "123", "uuid": "abc"},
        ]
        result = runner.invoke(app, ["peers", "export"])
        assert result.exit_code == 0

    def test_export_help(self) -> None:
        result = runner.invoke(app, ["peers", "export", "--help"])
        assert result.exit_code == 0
