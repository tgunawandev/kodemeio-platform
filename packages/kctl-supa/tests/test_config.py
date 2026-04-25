"""Tests for kctl-supa config module."""

from kctl_supa.core.config import ServiceConfig, SERVICE_KEY


def test_service_key():
    assert SERVICE_KEY == "supabase"


def test_service_config_defaults():
    cfg = ServiceConfig()
    assert cfg.url == ""
    assert cfg.service_role_key == ""
    assert cfg.anon_key == ""
    assert cfg.db_password == ""
    assert cfg.ssh_host == ""
    assert cfg.ssh_port == 22
    assert cfg.ssh_user == "root"
    assert cfg.ssh_key == "~/.ssh/id_ed25519"
    assert cfg.container_prefix == ""


def test_service_config_from_dict():
    cfg = ServiceConfig(
        url="https://supa.terakidz.com",
        service_role_key="test-key",
        container_prefix="terakidz-supabase",
    )
    assert cfg.url == "https://supa.terakidz.com"
    assert cfg.service_role_key == "test-key"
    assert cfg.container_prefix == "terakidz-supabase"
