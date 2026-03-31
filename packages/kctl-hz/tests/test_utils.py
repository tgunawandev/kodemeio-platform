"""Tests for shared utility functions."""

from __future__ import annotations

from kctl_hz.core.utils import (
    action_status_color,
    format_labels,
    human_size,
    mask_token,
    parse_labels,
    parse_price,
    server_status_color,
)


class TestServerStatusColor:
    def test_running(self) -> None:
        assert "[green]" in server_status_color("running")

    def test_off(self) -> None:
        assert "[dim]" in server_status_color("off")

    def test_unknown(self) -> None:
        assert server_status_color("unknown") == "unknown"


class TestActionStatusColor:
    def test_success(self) -> None:
        assert "[green]" in action_status_color("success")

    def test_error(self) -> None:
        assert "[red]" in action_status_color("error")


class TestFormatLabels:
    def test_empty(self) -> None:
        assert format_labels({}) == "-"
        assert format_labels(None) == "-"

    def test_single(self) -> None:
        assert format_labels({"env": "prod"}) == "env=prod"

    def test_sorted(self) -> None:
        result = format_labels({"env": "prod", "app": "web"})
        assert result == "app=web, env=prod"


class TestParseLabels:
    def test_basic(self) -> None:
        assert parse_labels("env=prod,app=web") == {"env": "prod", "app": "web"}

    def test_single(self) -> None:
        assert parse_labels("env=prod") == {"env": "prod"}

    def test_value_with_equals(self) -> None:
        assert parse_labels("config=key=value") == {"config": "key=value"}

    def test_whitespace_stripped(self) -> None:
        assert parse_labels(" env = prod , app = web ") == {"env": "prod", "app": "web"}

    def test_empty_key_skipped(self) -> None:
        assert parse_labels("=val,env=prod") == {"env": "prod"}

    def test_no_equals_skipped(self) -> None:
        assert parse_labels("invalid,env=prod") == {"env": "prod"}

    def test_empty_string(self) -> None:
        assert parse_labels("") == {}

    def test_empty_value_allowed(self) -> None:
        assert parse_labels("env=") == {"env": ""}


class TestHumanSize:
    def test_bytes(self) -> None:
        assert human_size(512) == "512.0 B"

    def test_kb(self) -> None:
        assert human_size(2048) == "2.0 KB"

    def test_gb(self) -> None:
        assert human_size(2 * 1024**3) == "2.0 GB"

    def test_tb(self) -> None:
        assert human_size(5 * 1024**4) == "5.0 TB"


class TestMaskToken:
    def test_long_token(self) -> None:
        result = mask_token("abcdefghijklmnop")
        assert result.startswith("abcd")
        assert result.endswith("mnop")
        assert "****" in result

    def test_short_token(self) -> None:
        assert mask_token("short") == "****"


class TestParsePrice:
    def test_normal(self) -> None:
        data = {"price_monthly": {"gross": "10.50"}}
        assert parse_price(data) == 10.50

    def test_missing(self) -> None:
        assert parse_price({}) == 0.0

    def test_invalid(self) -> None:
        assert parse_price({"price_monthly": "not a number"}) == 0.0
