"""Config round-trip + env expansion tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from kctl_gsc.core.config import (
    ServiceConfig,
    get_service_config,
    resolve_active_profile_name,
    resolve_connection,
    set_service_config,
)


@pytest.fixture
def tmp_cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cfg = tmp_path / "kodemeio" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    monkeypatch.setattr("kctl_gsc.core.config.CONFIG_FILE", cfg)
    monkeypatch.setattr("kctl_gsc.core.config.CONFIG_DIR", cfg.parent)
    return cfg


def test_roundtrip(tmp_cfg: Path) -> None:
    sc = ServiceConfig(
        credentials_file="~/.config/kodemeio/gsc-sa.json",
        default_property="sc-domain:kodeme.io",
    )
    set_service_config("kodemeio-kod-infra-gsc", sc)
    loaded = get_service_config("kodemeio-kod-infra-gsc")
    assert loaded.credentials_file == "~/.config/kodemeio/gsc-sa.json"
    assert loaded.default_property == "sc-domain:kodeme.io"


def test_env_expansion(tmp_cfg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GSC_CREDS", "/custom/path/sa.json")
    set_service_config(
        "kodemeio-kod-infra-gsc",
        ServiceConfig(credentials_file="${GSC_CREDS}", default_property="sc-domain:kodeme.io"),
    )
    creds_path, prop = resolve_connection(profile_name="kodemeio-kod-infra-gsc")
    assert creds_path == "/custom/path/sa.json"
    assert prop == "sc-domain:kodeme.io"


def test_resolve_active_profile_requires_source(tmp_cfg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KCTL_GSC_PROFILE", raising=False)
    with pytest.raises(ValueError, match="No profile"):
        resolve_active_profile_name(None)
