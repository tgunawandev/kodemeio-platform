"""Tests for kctl-redis keys commands."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from kctl_redis.cli import app
from kctl_redis.core.callbacks import AppContext
from kctl_redis.core.output import Output


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ctx(mock_client: MagicMock, json_mode: bool = False) -> AppContext:
    """Build an AppContext with a pre-injected mock client."""
    ctx = AppContext(quiet=True, json_mode=json_mode)
    ctx._client = mock_client
    return ctx


def invoke(runner: CliRunner, app_ctx: AppContext, args: list[str]) -> object:
    """Invoke CLI with the given AppContext injected via obj."""
    return runner.invoke(app, args, obj=app_ctx, catch_exceptions=False)


# ---------------------------------------------------------------------------
# keys scan
# ---------------------------------------------------------------------------


class TestKeysScan:
    def test_scan_empty_result(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.scan.return_value = (0, [])
        result = invoke(runner, make_ctx(mock_client), ["keys", "scan"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_scan_returns_keys(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.scan.return_value = (0, ["user:1", "user:2"])
        result = invoke(runner, make_ctx(mock_client), ["keys", "scan", "--pattern", "user:*"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_scan_iterates_until_cursor_zero(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.scan.side_effect = [
            (42, ["k1", "k2"]),
            (0, ["k3"]),
        ]
        result = invoke(runner, make_ctx(mock_client), ["keys", "scan", "--limit", "10"])
        assert result.exit_code == 0  # type: ignore[attr-defined]
        assert mock_client.r.scan.call_count == 2

    def test_scan_stops_at_limit(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.scan.side_effect = [
            (1, ["k1", "k2", "k3"]),
            (0, ["k4", "k5"]),
        ]
        result = invoke(runner, make_ctx(mock_client), ["keys", "scan", "--limit", "3"])
        assert result.exit_code == 0  # type: ignore[attr-defined]
        # Should stop after first call because limit=3 was reached
        assert mock_client.r.scan.call_count == 1

    def test_scan_with_type_filter_passes_kwarg(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.scan.return_value = (0, ["myhash"])
        result = invoke(runner, make_ctx(mock_client), ["keys", "scan", "--type", "hash"])
        assert result.exit_code == 0  # type: ignore[attr-defined]
        call_kwargs = mock_client.r.scan.call_args.kwargs
        assert call_kwargs.get("_type") == "hash"

    def test_scan_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.scan.return_value = (0, ["key:1"])
        result = invoke(runner, make_ctx(mock_client, json_mode=True), ["keys", "scan"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_scan_no_type_filter_omits_kwarg(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.scan.return_value = (0, [])
        invoke(runner, make_ctx(mock_client), ["keys", "scan"])
        call_kwargs = mock_client.r.scan.call_args.kwargs
        assert "_type" not in call_kwargs


# ---------------------------------------------------------------------------
# keys get
# ---------------------------------------------------------------------------


class TestKeysGet:
    def test_get_string(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.type.return_value = "string"
        mock_client.r.get.return_value = "hello"
        result = invoke(runner, make_ctx(mock_client), ["keys", "get", "mykey"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_get_hash(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.type.return_value = "hash"
        mock_client.r.hgetall.return_value = {"field": "value"}
        result = invoke(runner, make_ctx(mock_client), ["keys", "get", "myhash"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_get_list(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.type.return_value = "list"
        mock_client.r.lrange.return_value = ["a", "b", "c"]
        result = invoke(runner, make_ctx(mock_client), ["keys", "get", "mylist"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_get_set(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.type.return_value = "set"
        mock_client.r.smembers.return_value = {"x", "y"}
        result = invoke(runner, make_ctx(mock_client), ["keys", "get", "myset"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_get_zset(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.type.return_value = "zset"
        mock_client.r.zrange.return_value = [("m1", 1.0), ("m2", 2.0)]
        result = invoke(runner, make_ctx(mock_client), ["keys", "get", "myzset"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_get_stream(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.type.return_value = "stream"
        mock_client.r.xrange.return_value = [("1234-0", {"f": "v"})]
        result = invoke(runner, make_ctx(mock_client), ["keys", "get", "mystream"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_get_missing_key_exits_1(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.type.return_value = "none"
        result = runner.invoke(app, ["keys", "get", "ghost"], obj=make_ctx(mock_client))
        assert result.exit_code == 1  # type: ignore[attr-defined]

    def test_get_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.type.return_value = "string"
        mock_client.r.get.return_value = "world"
        result = invoke(runner, make_ctx(mock_client, json_mode=True), ["keys", "get", "hello"])
        assert result.exit_code == 0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# keys ttl
# ---------------------------------------------------------------------------


class TestKeysTtl:
    def test_ttl_persistent(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.ttl.return_value = -1
        result = invoke(runner, make_ctx(mock_client), ["keys", "ttl", "mykey"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_ttl_expiring(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.ttl.return_value = 300
        result = invoke(runner, make_ctx(mock_client), ["keys", "ttl", "mykey"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_ttl_missing_key(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.ttl.return_value = -2
        result = invoke(runner, make_ctx(mock_client), ["keys", "ttl", "missing"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_ttl_precise_uses_pttl(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.pttl.return_value = 12345
        result = invoke(runner, make_ctx(mock_client), ["keys", "ttl", "mykey", "--ms"])
        assert result.exit_code == 0  # type: ignore[attr-defined]
        mock_client.r.pttl.assert_called_once_with("mykey")

    def test_ttl_non_precise_uses_ttl(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.ttl.return_value = 60
        invoke(runner, make_ctx(mock_client), ["keys", "ttl", "mykey"])
        mock_client.r.ttl.assert_called_once_with("mykey")


# ---------------------------------------------------------------------------
# keys type
# ---------------------------------------------------------------------------


class TestKeysType:
    def test_type_string_key(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.type.return_value = "string"
        mock_client.r.object.return_value = "embstr"
        result = invoke(runner, make_ctx(mock_client), ["keys", "type", "mykey"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_type_none_key(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.type.return_value = "none"
        result = invoke(runner, make_ctx(mock_client), ["keys", "type", "missing"])
        assert result.exit_code == 0  # type: ignore[attr-defined]
        # Should NOT call object() for non-existent keys
        mock_client.r.object.assert_not_called()

    def test_type_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.type.return_value = "hash"
        mock_client.r.object.return_value = "ziplist"
        result = invoke(runner, make_ctx(mock_client, json_mode=True), ["keys", "type", "myhash"])
        assert result.exit_code == 0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# keys delete
# ---------------------------------------------------------------------------


class TestKeysDelete:
    def test_delete_with_force(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.exists.return_value = True
        result = invoke(runner, make_ctx(mock_client), ["keys", "delete", "mykey", "--force"])
        assert result.exit_code == 0  # type: ignore[attr-defined]
        mock_client.r.delete.assert_called_once_with("mykey")

    def test_delete_nonexistent_exits_1(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.exists.return_value = False
        result = runner.invoke(app, ["keys", "delete", "ghost", "--force"], obj=make_ctx(mock_client))
        assert result.exit_code == 1  # type: ignore[attr-defined]

    def test_delete_confirm_yes(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.exists.return_value = True
        result = runner.invoke(app, ["keys", "delete", "mykey"], obj=make_ctx(mock_client), input="y\n")
        assert result.exit_code == 0  # type: ignore[attr-defined]
        mock_client.r.delete.assert_called_once_with("mykey")

    def test_delete_confirm_no_aborts(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.exists.return_value = True
        result = runner.invoke(app, ["keys", "delete", "mykey"], obj=make_ctx(mock_client), input="n\n")
        assert result.exit_code != 0  # type: ignore[attr-defined]
        mock_client.r.delete.assert_not_called()


# ---------------------------------------------------------------------------
# keys memory-usage
# ---------------------------------------------------------------------------


class TestKeysMemoryUsage:
    def test_memory_usage_found(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.memory_usage.return_value = 512
        result = invoke(runner, make_ctx(mock_client), ["keys", "memory-usage", "mykey"])
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_memory_usage_missing_exits_1(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.memory_usage.return_value = None
        result = runner.invoke(app, ["keys", "memory-usage", "ghost"], obj=make_ctx(mock_client))
        assert result.exit_code == 1  # type: ignore[attr-defined]

    def test_memory_usage_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.memory_usage.return_value = 1024
        result = invoke(runner, make_ctx(mock_client, json_mode=True), ["keys", "memory-usage", "bigkey"])
        assert result.exit_code == 0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# keys rename
# ---------------------------------------------------------------------------


class TestKeysRename:
    def test_rename_success(self, runner: CliRunner, mock_client: MagicMock) -> None:
        # old exists, new does not
        mock_client.r.exists.side_effect = lambda k: k == "old"
        result = invoke(runner, make_ctx(mock_client), ["keys", "rename", "old", "new"])
        assert result.exit_code == 0  # type: ignore[attr-defined]
        mock_client.r.rename.assert_called_once_with("old", "new")

    def test_rename_old_missing_exits_1(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.r.exists.return_value = False
        result = runner.invoke(app, ["keys", "rename", "ghost", "new"], obj=make_ctx(mock_client))
        assert result.exit_code == 1  # type: ignore[attr-defined]

    def test_rename_overwrite_confirms(self, runner: CliRunner, mock_client: MagicMock) -> None:
        # Both keys exist — confirmation required
        mock_client.r.exists.return_value = True
        result = runner.invoke(app, ["keys", "rename", "old", "existing"], obj=make_ctx(mock_client), input="y\n")
        assert result.exit_code == 0  # type: ignore[attr-defined]
        mock_client.r.rename.assert_called_once_with("old", "existing")
