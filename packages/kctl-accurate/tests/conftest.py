"""Shared pytest fixtures for kctl_accurate."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


@pytest.fixture
def fake_config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ~/.config/kodemeio/config.yaml to a tmp dir."""
    config_dir = tmp_path / ".config" / "kodemeio"
    config_dir.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    import kctl_lib.config as klc

    monkeypatch.setattr(klc, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(klc, "CONFIG_FILE", config_dir / "config.yaml")
    return config_dir


@pytest.fixture
def write_profile(fake_config_home: Path):
    """Helper that writes a profile config in one call."""

    def _write(profile: str, accurate: dict, default: bool = True) -> None:
        data = {
            "default_profile": profile if default else "default",
            "profiles": {profile: {"accurate": accurate}},
        }
        (fake_config_home / "config.yaml").write_text(yaml.safe_dump(data))

    return _write
