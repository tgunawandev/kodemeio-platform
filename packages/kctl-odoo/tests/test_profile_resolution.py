"""Regression tests for profile resolution error messages."""

from __future__ import annotations

from pathlib import Path

import pytest
from kctl_lib.exceptions import ConfigError

from kctl_odoo.core import config as odoo_config


@pytest.fixture
def isolated_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the CLI at a temporary empty config file."""
    cfg_dir = tmp_path / "kodemeio"
    cfg_dir.mkdir()
    cfg_file = cfg_dir / "config.yaml"
    cfg_file.write_text(
        "default_profile: real-one\n"
        "profiles:\n"
        "  real-one:\n"
        "    odoo:\n"
        "      url: https://odoo.example\n"
        "      database: db\n"
        "      api_key: key\n"
        "  another:\n"
        "    odoo:\n"
        "      url: https://odoo2.example\n"
        "      database: db2\n"
        "      api_key: key2\n"
    )
    monkeypatch.setattr(odoo_config, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(odoo_config, "CONFIG_FILE", cfg_file)
    # Make sure env vars don't leak real credentials into the test
    for var in ("KCTL_ODOO_URL", "KCTL_ODOO_API_KEY", "KCTL_ODOO_DATABASE", "KCTL_ODOO_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    return cfg_file


def test_unknown_profile_raises_config_error(isolated_config: Path) -> None:
    with pytest.raises(ConfigError) as excinfo:
        odoo_config.resolve_connection(profile_name="does-not-exist")
    msg = str(excinfo.value)
    assert "'does-not-exist' not found" in msg
    assert "real-one" in msg
    assert "another" in msg


def test_known_profile_resolves(isolated_config: Path) -> None:
    url, database, _, api_key = odoo_config.resolve_connection(profile_name="real-one")
    assert url == "https://odoo.example"
    assert database == "db"
    assert api_key == "key"


def test_env_override_bypasses_missing_profile(monkeypatch: pytest.MonkeyPatch, isolated_config: Path) -> None:
    """Explicit URL env var should let commands run even with an unknown profile."""
    monkeypatch.setenv("KCTL_ODOO_URL", "https://override.example")
    monkeypatch.setenv("KCTL_ODOO_API_KEY", "override-key")
    monkeypatch.setenv("KCTL_ODOO_DATABASE", "override-db")
    url, database, _, api_key = odoo_config.resolve_connection(profile_name="does-not-exist")
    assert url == "https://override.example"
    assert database == "override-db"
    assert api_key == "override-key"
