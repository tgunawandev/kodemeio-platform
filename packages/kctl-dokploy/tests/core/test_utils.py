"""Tests for shared utility functions."""

from __future__ import annotations

from kctl_dokploy.core.utils import (
    fmt_duration,
    fmt_status,
    fmt_timestamp,
    human_size,
    status_icon,
    strip_rich_markup,
    truncate,
)


class TestStatusIcon:
    def test_running_is_green(self) -> None:
        assert "green" in status_icon("running")

    def test_done_is_green(self) -> None:
        assert "green" in status_icon("done")

    def test_error_is_red(self) -> None:
        assert "red" in status_icon("error")

    def test_stopped_is_yellow(self) -> None:
        assert "yellow" in status_icon("stopped")

    def test_unknown_is_blue(self) -> None:
        assert "blue" in status_icon("unknown")

    def test_case_insensitive(self) -> None:
        assert "green" in status_icon("Running")


class TestFmtStatus:
    def test_includes_icon_and_text(self) -> None:
        result = fmt_status("running")
        assert "running" in result
        assert "green" in result


class TestHumanSize:
    def test_bytes(self) -> None:
        assert human_size(500) == "500 B"

    def test_kilobytes(self) -> None:
        assert "KB" in human_size(1500)

    def test_megabytes(self) -> None:
        assert "MB" in human_size(1_500_000)

    def test_gigabytes(self) -> None:
        assert "GB" in human_size(1_500_000_000)

    def test_negative(self) -> None:
        assert human_size(-1) == "0 B"


class TestFmtDuration:
    def test_seconds(self) -> None:
        assert fmt_duration(45) == "45s"

    def test_minutes(self) -> None:
        assert fmt_duration(90) == "1m 30s"

    def test_hours(self) -> None:
        assert fmt_duration(3700) == "1h 1m"

    def test_exact_minutes(self) -> None:
        assert fmt_duration(120) == "2m"

    def test_negative(self) -> None:
        assert fmt_duration(-5) == "0s"


class TestFmtTimestamp:
    def test_none_returns_dash(self) -> None:
        assert fmt_timestamp(None) == "-"

    def test_empty_returns_dash(self) -> None:
        assert fmt_timestamp("") == "-"

    def test_invalid_returns_truncated(self) -> None:
        result = fmt_timestamp("not-a-date")
        assert isinstance(result, str)

    def test_valid_iso(self) -> None:
        result = fmt_timestamp("2020-01-01T00:00:00Z")
        assert isinstance(result, str)
        assert result != "-"


class TestTruncate:
    def test_short_unchanged(self) -> None:
        assert truncate("hello", 10) == "hello"

    def test_long_truncated(self) -> None:
        result = truncate("a" * 60, 20)
        assert len(result) == 20
        assert result.endswith("...")


class TestStripRichMarkup:
    def test_removes_tags(self) -> None:
        assert strip_rich_markup("[green]OK[/green]") == "OK"

    def test_no_tags_unchanged(self) -> None:
        assert strip_rich_markup("plain text") == "plain text"
