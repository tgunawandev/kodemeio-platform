"""Tests for profile configuration."""

from __future__ import annotations

from pathlib import Path

import yaml

from kctl_claw.core.config import (
    SERVICE_KEY,
    ServiceConfig,
    get_service_config,
    load_raw_config,
    resolve_project_root,
    save_raw_config,
)


def test_service_key():
    assert SERVICE_KEY == "claw"


def test_service_config_defaults():
    cfg = ServiceConfig()
    assert cfg.gateway_url == ""
    assert cfg.gateway_token == ""
    assert cfg.compose_file == "docker-compose.prod.yml"
    assert cfg.env_file == ".env.prod"


def test_save_and_load_config(tmp_path, monkeypatch):
    config_file = tmp_path / "config.yaml"
    monkeypatch.setattr("kctl_common.config.CONFIG_FILE", config_file)
    monkeypatch.setattr("kctl_common.config.CONFIG_DIR", tmp_path)

    save_raw_config(
        {
            "default_profile": "prod",
            "profiles": {
                "prod": {
                    "claw": {
                        "project_root": "/some/path",
                        "gateway_url": "https://openclaw.kodeme.io",
                    }
                }
            },
        }
    )

    data = load_raw_config()
    assert data["default_profile"] == "prod"


def test_get_service_config(tmp_path, monkeypatch):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        yaml.dump(
            {
                "default_profile": "default",
                "profiles": {
                    "default": {
                        "claw": {
                            "project_root": "/my/project",
                            "gateway_url": "https://openclaw.kodeme.io",
                            "gateway_token": "secret",
                        }
                    }
                },
            }
        )
    )
    monkeypatch.setattr("kctl_common.config.CONFIG_FILE", config_file)

    cfg = get_service_config("default")
    assert cfg.project_root == "/my/project"
    assert cfg.gateway_url == "https://openclaw.kodeme.io"
    assert cfg.gateway_token == "secret"


def test_resolve_project_root_override():
    root = resolve_project_root(root_override="/tmp/override")
    assert root == Path("/tmp/override")
