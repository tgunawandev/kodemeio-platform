"""Tests for kctl_accurate.core.config."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kctl_accurate.core.config import (
    SERVICE_KEY,
    ServiceConfig,
    mask_secret,
    resolve_connection,
)


def _write_config(config_dir: Path, data: dict) -> None:
    (config_dir / "config.yaml").write_text(yaml.safe_dump(data))


def test_service_key_is_accurate() -> None:
    assert SERVICE_KEY == "accurate"


def test_service_config_defaults_blank() -> None:
    cfg = ServiceConfig()
    assert cfg.api_token == ""
    assert cfg.signature_secret == ""
    assert cfg.db_id == 0
    assert cfg.host == ""
    assert cfg.db_alias == ""
    assert cfg.default_modified_since_days == 0


def test_mask_secret_short() -> None:
    assert mask_secret("") == "[dim]not set[/dim]"
    assert mask_secret("abcd") == "****"
    assert mask_secret("abcdefghi") == "****"  # 9 chars, still <10


def test_mask_secret_long() -> None:
    out = mask_secret("aut.abcdef.0123456789xyz")
    assert out.startswith("aut.")
    assert out.endswith("9xyz")
    assert "*" in out
    # original secret never appears in masked output (modulo the 4+4 keep)
    assert "abcdef.012345678" not in out


def test_resolve_uses_profile_config(fake_config_home: Path) -> None:
    _write_config(
        fake_config_home,
        {
            "default_profile": "tpp",
            "profiles": {
                "tpp": {
                    "accurate": {
                        "api_token": "token-from-file",
                        "signature_secret": "secret-from-file",
                        "db_id": 12345,
                    }
                }
            },
        },
    )
    cfg = resolve_connection(profile_name="tpp")
    assert cfg.api_token == "token-from-file"
    assert cfg.db_id == 12345


def test_resolve_env_overrides_file(fake_config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(
        fake_config_home,
        {
            "default_profile": "tpp",
            "profiles": {"tpp": {"accurate": {"api_token": "from-file", "signature_secret": "s", "db_id": 1}}},
        },
    )
    monkeypatch.setenv("KCTL_ACCURATE_API_TOKEN", "from-env")
    monkeypatch.setenv("KCTL_ACCURATE_DB_ID", "999")
    cfg = resolve_connection(profile_name="tpp")
    assert cfg.api_token == "from-env"
    assert cfg.db_id == 999


def test_resolve_cli_overrides_env(fake_config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(
        fake_config_home,
        {
            "default_profile": "tpp",
            "profiles": {"tpp": {"accurate": {"api_token": "f", "signature_secret": "s", "db_id": 1}}},
        },
    )
    monkeypatch.setenv("KCTL_ACCURATE_API_TOKEN", "from-env")
    cfg = resolve_connection(
        profile_name="tpp",
        api_token_override="from-cli",
        db_id_override=42,
    )
    assert cfg.api_token == "from-cli"
    assert cfg.db_id == 42


def test_resolve_missing_creds_returns_blanks(fake_config_home: Path) -> None:
    """resolve_connection itself doesn't raise — callers (e.g., the client
    constructor) decide what's required."""
    _write_config(fake_config_home, {"default_profile": "empty", "profiles": {"empty": {}}})
    cfg = resolve_connection(profile_name="empty")
    assert cfg.api_token == ""
    assert cfg.signature_secret == ""
    assert cfg.db_id == 0


def test_resolve_invalid_db_id_env_raises_config_error(fake_config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from kctl_lib.exceptions import ConfigError

    _write_config(
        fake_config_home,
        {
            "default_profile": "tpp",
            "profiles": {"tpp": {"accurate": {"api_token": "t", "signature_secret": "s", "db_id": 1}}},
        },
    )
    monkeypatch.setenv("KCTL_ACCURATE_DB_ID", "not-a-number")
    with pytest.raises(ConfigError) as exc_info:
        resolve_connection(profile_name="tpp")
    assert "KCTL_ACCURATE_DB_ID" in str(exc_info.value)
