"""Tests for kctl_lib.callbacks."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

from kctl_lib.callbacks import AppContextBase
from kctl_lib.output import Output


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


class TestMockOutput:
    def test_mock_output_json_mode(self) -> None:
        from kctl_lib.testing import mock_output

        out = mock_output()
        assert out.json_mode is True
        assert out.format == "json"

    def test_mock_app_context(self) -> None:
        from kctl_lib.testing import mock_app_context

        ctx = mock_app_context(quiet=True)
        assert ctx.quiet is True
        assert ctx.output.quiet is True

    def test_temp_config(self, tmp_path: Path) -> None:
        from kctl_lib.testing import temp_config

        profiles = {"default": {"next": {"project_root": "/test"}}}
        path = temp_config(profiles, base_dir=tmp_path)
        assert path.exists()


class TestBannerEmission:
    def test_emit_banner_writes_to_stderr(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_lib.callbacks import AppContextBase

        buf = io.StringIO()
        monkeypatch.setattr(sys, "stderr", buf)

        ctx = AppContextBase(profile="idtpp")
        ctx.emit_banner(
            app="kctl-dokploy",
            inheritance_chain=["idtpp"],
            service_summary="https://dokploy.idtpp.com",
        )

        out = buf.getvalue()
        assert "kctl-dokploy" in out
        assert "idtpp" in out

    def test_quiet_suppresses_banner(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_lib.callbacks import AppContextBase

        buf = io.StringIO()
        monkeypatch.setattr(sys, "stderr", buf)

        ctx = AppContextBase(profile="idtpp", quiet=True)
        ctx.emit_banner(
            app="kctl-dokploy",
            inheritance_chain=["idtpp"],
            service_summary=None,
        )

        assert buf.getvalue() == ""

    def test_json_mode_suppresses_stderr_banner(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_lib.callbacks import AppContextBase

        buf = io.StringIO()
        monkeypatch.setattr(sys, "stderr", buf)

        ctx = AppContextBase(profile="idtpp", json_mode=True)
        ctx.emit_banner(
            app="kctl-dokploy",
            inheritance_chain=["idtpp"],
            service_summary=None,
        )

        # In JSON mode the banner should not go to stderr; consumers
        # embed `_profile` in the stdout JSON body instead.
        assert buf.getvalue() == ""

    def test_emit_once_even_if_called_twice(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_lib.callbacks import AppContextBase

        buf = io.StringIO()
        monkeypatch.setattr(sys, "stderr", buf)

        ctx = AppContextBase(profile="idtpp")
        ctx.emit_banner(app="kctl-x", inheritance_chain=["idtpp"], service_summary=None)
        first = buf.getvalue()
        ctx.emit_banner(app="kctl-x", inheritance_chain=["idtpp"], service_summary=None)
        second = buf.getvalue()

        assert first == second  # second call was a no-op
