"""Tests for kctl_common.plugins."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import typer

from kctl_common.plugins import KctlPlugin, discover_and_load_plugins


class TestKctlPluginProtocol:
    def test_protocol_accepts_valid_class(self) -> None:
        class MyPlugin:
            name = "test"

            def register(self, app: typer.Typer) -> None:
                pass

        plugin = MyPlugin()
        assert plugin.name == "test"


class TestDiscoverAndLoad:
    def test_empty_when_no_plugins(self) -> None:
        app = typer.Typer()
        with patch("kctl_common.plugins.importlib.metadata.entry_points", return_value=[]):
            loaded = discover_and_load_plugins(app, "kctl_test.plugins")
        assert loaded == []

    def test_loads_valid_plugin(self) -> None:
        app = typer.Typer()

        class FakePlugin:
            name = "fake"

            def register(self, app: typer.Typer) -> None:
                pass

        ep = MagicMock()
        ep.name = "fake"
        ep.load.return_value = FakePlugin
        with patch("kctl_common.plugins.importlib.metadata.entry_points", return_value=[ep]):
            loaded = discover_and_load_plugins(app, "kctl_test.plugins")
        assert loaded == ["fake"]

    def test_skips_broken_plugin(self) -> None:
        app = typer.Typer()
        ep = MagicMock()
        ep.name = "broken"
        ep.load.side_effect = ImportError("missing dep")
        with patch("kctl_common.plugins.importlib.metadata.entry_points", return_value=[ep]):
            loaded = discover_and_load_plugins(app, "kctl_test.plugins")
        assert loaded == []
