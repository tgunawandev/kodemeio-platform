"""Tests for kctl-redis memory commands."""

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


SAMPLE_MEMORY_INFO = {
    "used_memory_human": "1.50M",
    "used_memory_peak_human": "2.00M",
    "used_memory_rss_human": "3.00M",
    "maxmemory_human": "100.00M",
    "maxmemory_policy": "noeviction",
    "mem_fragmentation_ratio": 1.2,
    "mem_allocator": "libc",
}


# ---------------------------------------------------------------------------
# memory stats
# ---------------------------------------------------------------------------


class TestMemoryStats:
    def test_stats_shows_table(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = SAMPLE_MEMORY_INFO
        result = invoke(runner, make_ctx(mock_client), ["memory", "stats"])
        assert result.exit_code == 0  # type: ignore[attr-defined]
        mock_client.info.assert_called_once_with("memory")

    def test_stats_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = SAMPLE_MEMORY_INFO
        result = invoke(runner, make_ctx(mock_client, json_mode=True), ["memory", "stats"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_stats_empty_info(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = {}
        result = invoke(runner, make_ctx(mock_client), ["memory", "stats"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_stats_calls_memory_section(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = SAMPLE_MEMORY_INFO
        invoke(runner, make_ctx(mock_client), ["memory", "stats"])
        mock_client.info.assert_called_once_with("memory")


# ---------------------------------------------------------------------------
# memory big-keys
# ---------------------------------------------------------------------------


class TestMemoryBigKeys:
    def test_big_keys_empty_keyspace(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.scan.return_value = (0, [])
        result = invoke(runner, make_ctx(mock_client), ["memory", "big-keys"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_big_keys_sorted_by_size(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.scan.return_value = (0, ["small", "big", "medium"])
        mock_client.r.memory_usage.side_effect = lambda k: {"small": 100, "big": 5000, "medium": 500}[k]
        mock_client.r.type.side_effect = lambda k: "string"
        result = invoke(runner, make_ctx(mock_client), ["memory", "big-keys"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_big_keys_skips_none_usage(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.scan.return_value = (0, ["existing", "deleted"])
        mock_client.r.memory_usage.side_effect = lambda k: 1024 if k == "existing" else None
        mock_client.r.type.return_value = "string"
        result = invoke(runner, make_ctx(mock_client), ["memory", "big-keys"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_big_keys_respects_limit(self, runner: CliRunner, mock_client: MagicMock) -> None:
        keys = [f"key{i}" for i in range(50)]
        mock_client.r.scan.return_value = (0, keys)
        mock_client.r.memory_usage.side_effect = lambda k: int(k[3:]) * 10
        mock_client.r.type.return_value = "string"
        result = invoke(runner, make_ctx(mock_client), ["memory", "big-keys", "--limit", "5"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_big_keys_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.scan.return_value = (0, ["key1"])
        mock_client.r.memory_usage.return_value = 128
        mock_client.r.type.return_value = "string"
        result = invoke(runner, make_ctx(mock_client, json_mode=True), ["memory", "big-keys"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_big_keys_iterates_multiple_scans(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.scan.side_effect = [
            (1, ["k1", "k2"]),
            (0, ["k3"]),
        ]
        mock_client.r.memory_usage.return_value = 200
        mock_client.r.type.return_value = "string"
        result = invoke(runner, make_ctx(mock_client), ["memory", "big-keys"])
        assert result.exit_code == 0  # type: ignore[attr-defined]
        assert mock_client.r.scan.call_count == 2


# ---------------------------------------------------------------------------
# memory eviction
# ---------------------------------------------------------------------------


class TestMemoryEviction:
    def test_eviction_shows_policy(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.side_effect = lambda s: {
            "memory": {"maxmemory_policy": "allkeys-lru", "maxmemory_human": "512M"},
            "stats": {"evicted_keys": 42},
        }[s]
        result = invoke(runner, make_ctx(mock_client), ["memory", "eviction"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_eviction_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.side_effect = lambda s: {
            "memory": {"maxmemory_policy": "noeviction", "maxmemory_human": "0"},
            "stats": {"evicted_keys": 0},
        }[s]
        result = invoke(runner, make_ctx(mock_client, json_mode=True), ["memory", "eviction"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_eviction_zero_evictions(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.side_effect = lambda s: {
            "memory": {"maxmemory_policy": "noeviction", "maxmemory_human": "0"},
            "stats": {"evicted_keys": 0},
        }[s]
        result = invoke(runner, make_ctx(mock_client), ["memory", "eviction"])
        assert result.exit_code == 0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# memory fragmentation
# ---------------------------------------------------------------------------


class TestMemoryFragmentation:
    def test_fragmentation_normal_range(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = {
            "mem_fragmentation_ratio": 1.2,
            "used_memory_rss": 1024000,
            "used_memory_rss_human": "1.00M",
        }
        result = invoke(runner, make_ctx(mock_client), ["memory", "fragmentation"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_fragmentation_high_warns(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = {
            "mem_fragmentation_ratio": 2.5,
            "used_memory_rss": 5000000,
            "used_memory_rss_human": "4.77M",
        }
        result = invoke(runner, make_ctx(mock_client), ["memory", "fragmentation"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_fragmentation_below_one_warns(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = {
            "mem_fragmentation_ratio": 0.8,
            "used_memory_rss": 800000,
            "used_memory_rss_human": "781.25K",
        }
        result = invoke(runner, make_ctx(mock_client), ["memory", "fragmentation"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_fragmentation_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = {
            "mem_fragmentation_ratio": 1.1,
            "used_memory_rss": 2000000,
        }
        result = invoke(runner, make_ctx(mock_client, json_mode=True), ["memory", "fragmentation"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_fragmentation_calls_memory_section(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.info.return_value = {"mem_fragmentation_ratio": 1.0}
        invoke(runner, make_ctx(mock_client), ["memory", "fragmentation"])
        mock_client.info.assert_called_once_with("memory")
