"""Tests for core/output.py — Output class with aliases."""

from __future__ import annotations

from kctl_claude.core.output import Output


class TestOutput:
    def test_ok_alias(self) -> None:
        out = Output(quiet=True)
        # Should not raise
        out.ok("test")

    def test_fail_alias(self) -> None:
        out = Output()
        # Should not raise
        out.fail("test")

    def test_dim(self) -> None:
        out = Output()
        out.dim("dimmed text")

    def test_dim_quiet(self) -> None:
        out = Output(quiet=True)
        out.dim("should not print")

    def test_print_alias(self) -> None:
        out = Output()
        out.print("test text")

    def test_json_out_alias(self) -> None:
        out = Output(json_mode=True)
        out.json_out({"key": "value"})

    def test_json_mode_initialization(self) -> None:
        out = Output(json_mode=True)
        assert out.json_mode is True

    def test_quiet_initialization(self) -> None:
        out = Output(quiet=True)
        assert out.quiet is True
