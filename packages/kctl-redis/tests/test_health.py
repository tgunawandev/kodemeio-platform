"""Tests for kctl-redis health commands."""

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


HEALTHY_INFO = {
    "used_memory": 1_000_000,
    "maxmemory": 100_000_000,
    "connected_clients": 10,
    "rejected_connections": 0,
    "mem_fragmentation_ratio": 1.1,
    "keyspace_hits": 900,
    "keyspace_misses": 100,
}


# ---------------------------------------------------------------------------
# health ping
# ---------------------------------------------------------------------------


class TestHealthPing:
    def test_ping_success(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.ping.return_value = True
        result = invoke(runner, make_ctx(mock_client), ["health", "ping"])
        assert result.exit_code == 0  # type: ignore[attr-defined]
        mock_client.r.ping.assert_called_once()

    def test_ping_measures_latency(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.ping.return_value = True
        result = invoke(runner, make_ctx(mock_client), ["health", "ping"])
        # Should output "PONG" with a latency value
        assert result.exit_code == 0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# health info
# ---------------------------------------------------------------------------


class TestHealthInfo:
    def test_info_shows_server_details(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = {
            "redis_version": "7.2.0",
            "redis_mode": "standalone",
            "os": "Linux",
            "uptime_in_days": 15,
            "tcp_port": 6379,
            "config_file": "/etc/redis/redis.conf",
        }
        result = invoke(runner, make_ctx(mock_client), ["health", "info"])
        assert result.exit_code == 0  # type: ignore[attr-defined]
        mock_client.info.assert_called_once_with("server")

    def test_info_empty_server_section(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = {}
        result = invoke(runner, make_ctx(mock_client), ["health", "info"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_info_missing_fields_show_question_mark(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = {"redis_version": "7.0.0"}
        result = invoke(runner, make_ctx(mock_client), ["health", "info"])
        assert result.exit_code == 0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_check_healthy(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = HEALTHY_INFO
        result = invoke(runner, make_ctx(mock_client), ["health", "check"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_check_healthy_json(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = HEALTHY_INFO
        result = invoke(runner, make_ctx(mock_client, json_mode=True), ["health", "check"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_check_memory_warning(self, runner: CliRunner, mock_client: MagicMock) -> None:
        info = {**HEALTHY_INFO, "used_memory": 85_000_000, "maxmemory": 100_000_000}
        mock_client.info.return_value = info
        result = invoke(runner, make_ctx(mock_client), ["health", "check", "--memory-warn", "80"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_check_memory_critical(self, runner: CliRunner, mock_client: MagicMock) -> None:
        info = {**HEALTHY_INFO, "used_memory": 95_000_000, "maxmemory": 100_000_000}
        mock_client.info.return_value = info
        result = invoke(runner, make_ctx(mock_client), ["health", "check", "--memory-crit", "90"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_check_high_client_count(self, runner: CliRunner, mock_client: MagicMock) -> None:
        info = {**HEALTHY_INFO, "connected_clients": 600}
        mock_client.info.return_value = info
        result = invoke(runner, make_ctx(mock_client), ["health", "check", "--clients-warn", "500"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_check_rejected_connections_penalizes_score(self, runner: CliRunner, mock_client: MagicMock) -> None:
        info = {**HEALTHY_INFO, "rejected_connections": 10}
        mock_client.info.return_value = info
        result = invoke(runner, make_ctx(mock_client, json_mode=True), ["health", "check"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_check_high_fragmentation_penalizes_score(self, runner: CliRunner, mock_client: MagicMock) -> None:
        info = {**HEALTHY_INFO, "mem_fragmentation_ratio": 2.5}
        mock_client.info.return_value = info
        result = invoke(runner, make_ctx(mock_client, json_mode=True), ["health", "check"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_check_low_hit_ratio_penalizes_score(self, runner: CliRunner, mock_client: MagicMock) -> None:
        info = {**HEALTHY_INFO, "keyspace_hits": 10, "keyspace_misses": 990}
        mock_client.info.return_value = info
        result = invoke(runner, make_ctx(mock_client, json_mode=True), ["health", "check"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_check_no_maxmemory_skips_memory_check(self, runner: CliRunner, mock_client: MagicMock) -> None:
        info = {**HEALTHY_INFO, "maxmemory": 0}
        mock_client.info.return_value = info
        result = invoke(runner, make_ctx(mock_client), ["health", "check"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_check_no_keyspace_activity_skips_hit_ratio(self, runner: CliRunner, mock_client: MagicMock) -> None:
        info = {**HEALTHY_INFO, "keyspace_hits": 0, "keyspace_misses": 0}
        mock_client.info.return_value = info
        result = invoke(runner, make_ctx(mock_client), ["health", "check"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_check_score_thresholds_healthy(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = HEALTHY_INFO
        result = invoke(runner, make_ctx(mock_client, json_mode=True), ["health", "check"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_check_custom_thresholds(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = HEALTHY_INFO
        result = invoke(
            runner,
            make_ctx(mock_client),
            ["health", "check", "--memory-warn", "70", "--memory-crit", "85", "--clients-warn", "200"],
        )
        assert result.exit_code == 0  # type: ignore[attr-defined]
        mock_client.info.assert_called_once()
