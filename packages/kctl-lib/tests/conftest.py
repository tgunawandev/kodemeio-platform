"""Shared test configuration."""

from __future__ import annotations

from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "real_config: test reads/writes the real ~/.config/kodemeio/config.yaml",
    )


@pytest.fixture(autouse=True)
def _isolate_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """Route all CONFIG_FILE reads/writes to tmp_path.

    Tests that need the real user config (integration only) must mark
    themselves with `@pytest.mark.real_config` to opt out.
    """
    if request.node.get_closest_marker("real_config"):
        return
    target = tmp_path / "config.yaml"
    monkeypatch.setattr("kctl_lib.config.CONFIG_FILE", target, raising=False)
    monkeypatch.setattr("kctl_lib.config.CONFIG_DIR", tmp_path, raising=False)
