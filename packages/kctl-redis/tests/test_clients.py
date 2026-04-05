"""Tests for kctl-redis clients commands."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from kctl_redis.cli import app
from kctl_redis.core.callbacks import AppContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ctx(mock_client: MagicMock, json_mode: bool = False) -> AppContext:
    ctx = AppContext(quiet=True, json_mode=json_mode)
    ctx._client = mock_client
    return ctx


def invoke(runner: CliRunner, app_ctx: AppContext, args: list[str]) -> object:
    return runner.invoke(app, args, obj=app_ctx, catch_exceptions=False)


# ---------------------------------------------------------------------------
# clients list
# ---------------------------------------------------------------------------


class TestClientsList:
    def test_list_empty(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.client_list.return_value = []
        result = invoke(runner, make_ctx(mock_client), ["clients", "list"])
        assert result.exit_code == 0  # type: ignore[attr-defined]
        mock_client.r.client_list.assert_called_once()

    def test_list_multiple_clients(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.client_list.return_value = [
            {"id": "1", "addr": "127.0.0.1:50001", "name": "", "age": "0", "idle": "0", "db": "0", "cmd": "client"},
            {"id": "2", "addr": "127.0.0.1:50002", "name": "worker", "age": "5", "idle": "2", "db": "1", "cmd": "get"},
        ]
        result = invoke(runner, make_ctx(mock_client), ["clients", "list"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_list_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.client_list.return_value = [
            {"id": "1", "addr": "127.0.0.1:50001", "name": "test"},
        ]
        result = invoke(runner, make_ctx(mock_client, json_mode=True), ["clients", "list"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_list_partial_client_fields(self, runner: CliRunner, mock_client: MagicMock) -> None:
        # Test that missing fields gracefully fall back to "?"
        mock_client.r.client_list.return_value = [{"id": "99"}]
        result = invoke(runner, make_ctx(mock_client), ["clients", "list"])
        assert result.exit_code == 0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# clients kill
# ---------------------------------------------------------------------------


class TestClientsKill:
    def test_kill_client(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.client_kill_filter.return_value = 1
        result = invoke(runner, make_ctx(mock_client), ["clients", "kill", "42"])
        assert result.exit_code == 0  # type: ignore[attr-defined]
        mock_client.r.client_kill_filter.assert_called_once_with(_id=42)

    def test_kill_outputs_success_message(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.client_kill_filter.return_value = 1
        result = invoke(runner, make_ctx(mock_client), ["clients", "kill", "7"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_kill_uses_integer_id(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.client_kill_filter.return_value = 1
        invoke(runner, make_ctx(mock_client), ["clients", "kill", "123"])
        call_kwargs = mock_client.r.client_kill_filter.call_args.kwargs
        assert call_kwargs["_id"] == 123
        assert isinstance(call_kwargs["_id"], int)


# ---------------------------------------------------------------------------
# clients info
# ---------------------------------------------------------------------------


class TestClientsInfo:
    def test_info_shows_metrics(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = {
            "connected_clients": 5,
            "blocked_clients": 0,
            "maxclients": 10000,
        }
        result = invoke(runner, make_ctx(mock_client), ["clients", "info"])
        assert result.exit_code == 0  # type: ignore[attr-defined]
        mock_client.info.assert_called_once_with("clients")

    def test_info_empty_section(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = {}
        result = invoke(runner, make_ctx(mock_client), ["clients", "info"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_info_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = {"connected_clients": 3}
        result = invoke(runner, make_ctx(mock_client, json_mode=True), ["clients", "info"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_info_calls_clients_section(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = {"connected_clients": 1}
        invoke(runner, make_ctx(mock_client), ["clients", "info"])
        mock_client.info.assert_called_once_with("clients")
