"""Tests for kctl_common.callbacks."""

from __future__ import annotations

from kctl_common.callbacks import AppContextBase
from kctl_common.output import Output


class TestAppContextBase:
    def test_defaults(self) -> None:
        ctx = AppContextBase()
        assert ctx.json_mode is False
        assert ctx.quiet is False
        assert ctx.profile is None
        assert ctx.format == "pretty"
        assert ctx.no_header is False

    def test_lazy_output(self) -> None:
        ctx = AppContextBase(json_mode=True, quiet=True)
        out = ctx.output
        assert isinstance(out, Output)
        assert out.json_mode is True
        assert out.quiet is True

    def test_output_cached(self) -> None:
        ctx = AppContextBase()
        out1 = ctx.output
        out2 = ctx.output
        assert out1 is out2

    def test_custom_values(self) -> None:
        ctx = AppContextBase(format="csv", no_header=True, profile="prod")
        assert ctx.format == "csv"
        assert ctx.no_header is True
        assert ctx.profile == "prod"
        out = ctx.output
        assert out.format == "csv"
        assert out.no_header is True
