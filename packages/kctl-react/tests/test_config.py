"""Tests for core/config.py and core/discovery.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from kctl_react.core.config import (
    SERVICE_KEY,
    ServiceConfig,
    get_default_profile,
    get_profile_names,
    get_service_config,
    load_raw_config,
    resolve_project_root,
    save_raw_config,
    set_default_profile,
    set_service_config,
)
from kctl_react.core.discovery import discover_apps, discover_packages, get_monorepo_scope
from kctl_react.core.exceptions import AppNotFoundError


class TestDiscovery:
    def test_discover_apps(self, mock_monorepo: Path) -> None:
        apps = discover_apps(mock_monorepo)
        assert len(apps) == 11
        assert "sfa" in apps
        assert apps["sfa"]["package"] == "@kodemeio/sfa"

    def test_discover_apps_extracts_port(self, mock_monorepo: Path) -> None:
        apps = discover_apps(mock_monorepo)
        # mock_monorepo uses "vite --port XXXX" in dev scripts
        for info in apps.values():
            assert isinstance(info["port"], int)

    def test_discover_packages(self, mock_monorepo: Path) -> None:
        packages = discover_packages(mock_monorepo)
        assert "core" in packages
        assert "ui" in packages

    def test_discover_apps_empty_dir(self, tmp_path: Path) -> None:
        (tmp_path / "apps").mkdir()
        apps = discover_apps(tmp_path)
        assert apps == {}

    def test_discover_apps_no_apps_dir(self, tmp_path: Path) -> None:
        apps = discover_apps(tmp_path)
        assert apps == {}

    def test_discover_packages_no_dir(self, tmp_path: Path) -> None:
        packages = discover_packages(tmp_path)
        assert packages == []

    def test_get_monorepo_scope(self, mock_monorepo: Path) -> None:
        # mock_monorepo has apps with @kodemeio/* names
        scope = get_monorepo_scope(mock_monorepo)
        assert scope == "@kodemeio"


class TestAppContext:
    def test_validate_app_valid(self, mock_monorepo: Path) -> None:
        from kctl_react.core.callbacks import AppContext

        actx = AppContext(root_override=str(mock_monorepo))
        actx.validate_app("sfa")  # Should not raise

    def test_validate_app_invalid(self, mock_monorepo: Path) -> None:
        from kctl_react.core.callbacks import AppContext

        actx = AppContext(root_override=str(mock_monorepo))
        with pytest.raises(AppNotFoundError) as exc_info:
            actx.validate_app("nonexistent")
        assert "nonexistent" in str(exc_info.value)

    def test_app_names(self, mock_monorepo: Path) -> None:
        from kctl_react.core.callbacks import AppContext

        actx = AppContext(root_override=str(mock_monorepo))
        assert len(actx.app_names) == 11
        assert "sfa" in actx.app_names

    def test_packages(self, mock_monorepo: Path) -> None:
        from kctl_react.core.callbacks import AppContext

        actx = AppContext(root_override=str(mock_monorepo))
        assert "core" in actx.packages


class TestServiceConfig:
    def test_defaults(self) -> None:
        cfg = ServiceConfig()
        assert cfg.project_root == ""
        assert cfg.api_url == ""
        assert cfg.odoo_url == ""
        assert cfg.odoo_db == ""


class TestConfigFile:
    def test_load_empty(self, mock_config: Path) -> None:
        assert load_raw_config() == {}

    def test_save_and_load(self, mock_config: Path) -> None:
        data = {"default_profile": "test", "profiles": {"test": {"react": {"project_root": "/tmp"}}}}
        save_raw_config(data)
        loaded = load_raw_config()
        assert loaded["default_profile"] == "test"

    def test_set_and_get_service_config(self, mock_config: Path) -> None:
        svc = ServiceConfig(project_root="/tmp/mono", api_url="https://api.kodeme.io")
        set_service_config("myprofile", svc)
        loaded = get_service_config("myprofile")
        assert loaded.project_root == "/tmp/mono"
        assert loaded.api_url == "https://api.kodeme.io"

    def test_get_missing_profile(self, mock_config: Path) -> None:
        svc = get_service_config("nonexistent")
        assert svc.project_root == ""

    def test_profile_names(self, mock_config: Path) -> None:
        set_service_config("alpha", ServiceConfig(project_root="/a"))
        set_service_config("beta", ServiceConfig(project_root="/b"))
        names = get_profile_names()
        assert "alpha" in names
        assert "beta" in names

    def test_default_profile(self, mock_config: Path) -> None:
        set_service_config("prod", ServiceConfig(project_root="/p"))
        set_default_profile("prod")
        assert get_default_profile() == "prod"

    def test_service_key(self) -> None:
        assert SERVICE_KEY == "react"

    def test_corrupt_yaml_warns(self, mock_config: Path) -> None:
        mock_config.write_text("{ invalid yaml: [")
        result = load_raw_config()
        assert result == {}


class TestResolveProjectRoot:
    def test_from_override(self, tmp_path: Path) -> None:
        root = resolve_project_root(root_override=str(tmp_path))
        assert root == tmp_path

    def test_from_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KCTL_REACT_ROOT", str(tmp_path))
        root = resolve_project_root()
        assert root == tmp_path

    def test_auto_detect(self, mock_monorepo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(mock_monorepo / "apps" / "sfa")
        monkeypatch.delenv("KCTL_REACT_ROOT", raising=False)
        root = resolve_project_root()
        assert root == mock_monorepo
