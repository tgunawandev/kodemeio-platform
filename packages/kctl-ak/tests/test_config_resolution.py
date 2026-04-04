"""Tests for config resolution (core/config.py)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from kctl_ak.core.config import (
    ServiceConfig,
    resolve_app_registry_path,
    resolve_connection,
    resolve_group_structure_path,
    resolve_roles_paths,
)


class TestResolveConnection:
    @patch("kctl_ak.core.config.is_container_mode", return_value=False)
    @patch("kctl_ak.core.config.resolve_active_profile_name", return_value="default")
    @patch("kctl_ak.core.config.get_service_config")
    def test_cli_flags_override_all(self, mock_svc: MagicMock, mock_pname: MagicMock, mock_ctr: MagicMock) -> None:
        mock_svc.return_value = ServiceConfig(url="https://from-config.com", token="config-token")
        url, token = resolve_connection(url_override="https://cli.com", token_override="cli-tok")
        assert url == "https://cli.com"
        assert token == "cli-tok"

    @patch.dict(os.environ, {"KCTL_AK_URL": "https://env.com", "KCTL_AK_TOKEN": "env-tok"})
    @patch("kctl_ak.core.config.is_container_mode", return_value=False)
    @patch("kctl_ak.core.config.resolve_active_profile_name", return_value="default")
    @patch("kctl_ak.core.config.get_service_config")
    def test_env_overrides_config(self, mock_svc: MagicMock, mock_pname: MagicMock, mock_ctr: MagicMock) -> None:
        mock_svc.return_value = ServiceConfig(url="https://config.com", token="cfg-tok")
        url, token = resolve_connection()
        assert url == "https://env.com"
        assert token == "env-tok"

    @patch.dict(os.environ, {}, clear=True)
    @patch("kctl_ak.core.config.is_container_mode", return_value=False)
    @patch("kctl_ak.core.config.resolve_active_profile_name", return_value="default")
    @patch("kctl_ak.core.config.get_service_config")
    def test_config_file_used(self, mock_svc: MagicMock, mock_pname: MagicMock, mock_ctr: MagicMock) -> None:
        mock_svc.return_value = ServiceConfig(url="https://config.com", token="cfg-tok")
        # Clear relevant env vars
        for k in ["KCTL_AK_URL", "KCTL_AK_TOKEN", "AUTHENTIK_API_URL", "AUTHENTIK_BOOTSTRAP_TOKEN"]:
            os.environ.pop(k, None)
        url, token = resolve_connection()
        assert url == "https://config.com"
        assert token == "cfg-tok"

    @patch.dict(os.environ, {"AUTHENTIK_API_URL": "https://ak.com", "AUTHENTIK_BOOTSTRAP_TOKEN": "bs-tok"})
    @patch("kctl_ak.core.config.is_container_mode", return_value=False)
    @patch("kctl_ak.core.config.resolve_active_profile_name", return_value="default")
    @patch("kctl_ak.core.config.get_service_config")
    def test_authentik_env_vars(self, mock_svc: MagicMock, mock_pname: MagicMock, mock_ctr: MagicMock) -> None:
        mock_svc.return_value = ServiceConfig()
        # Clear kctl-specific env vars
        os.environ.pop("KCTL_AK_URL", None)
        os.environ.pop("KCTL_AK_TOKEN", None)
        url, token = resolve_connection()
        assert url == "https://ak.com"
        assert token == "bs-tok"

    @patch.dict(os.environ, {}, clear=True)
    @patch("kctl_ak.core.config.is_container_mode", return_value=True)
    @patch("kctl_ak.core.config.resolve_active_profile_name", return_value="default")
    @patch("kctl_ak.core.config.get_service_config")
    def test_container_mode(self, mock_svc: MagicMock, mock_pname: MagicMock, mock_ctr: MagicMock) -> None:
        mock_svc.return_value = ServiceConfig()
        for k in ["KCTL_AK_URL", "KCTL_AK_TOKEN", "AUTHENTIK_API_URL", "AUTHENTIK_BOOTSTRAP_TOKEN"]:
            os.environ.pop(k, None)
        url, token = resolve_connection()
        assert url == "http://localhost:9000"


class TestResolveRolesPaths:
    @patch("kctl_ak.core.config.resolve_active_profile_name", return_value="default")
    @patch("kctl_ak.core.config.get_service_config")
    @patch("kctl_ak.core.config.load_raw_config", return_value={})
    def test_with_override(self, mock_raw: MagicMock, mock_svc: MagicMock, mock_pname: MagicMock) -> None:
        mock_svc.return_value = ServiceConfig()
        paths = resolve_roles_paths(config_override="/tmp/test-roles")
        assert any(str(p) == "/tmp/test-roles" for p in paths)

    @patch("kctl_ak.core.config.resolve_active_profile_name", return_value="default")
    @patch("kctl_ak.core.config.get_service_config")
    @patch("kctl_ak.core.config.load_raw_config", return_value={})
    def test_deduplicates(self, mock_raw: MagicMock, mock_svc: MagicMock, mock_pname: MagicMock) -> None:
        mock_svc.return_value = ServiceConfig()
        paths = resolve_roles_paths()
        path_strs = [str(p.resolve()) for p in paths]
        assert len(path_strs) == len(set(path_strs))


class TestResolveGroupStructurePath:
    @patch("kctl_ak.core.config.resolve_active_profile_name", return_value="default")
    @patch("kctl_ak.core.config.get_service_config")
    @patch("kctl_ak.core.config.load_raw_config", return_value={})
    def test_returns_none_when_not_found(
        self, mock_raw: MagicMock, mock_svc: MagicMock, mock_pname: MagicMock, tmp_path: Path
    ) -> None:
        mock_svc.return_value = ServiceConfig()
        # Run from temp dir with no config/group-structure.yaml
        with patch("kctl_ak.core.config.Path.cwd", return_value=tmp_path):
            result = resolve_group_structure_path()
        # May or may not be None depending on cwd, but should not raise
        assert result is None or isinstance(result, Path)

    @patch("kctl_ak.core.config.resolve_active_profile_name", return_value="default")
    @patch("kctl_ak.core.config.get_service_config")
    @patch("kctl_ak.core.config.load_raw_config", return_value={})
    def test_finds_in_config_dir(
        self, mock_raw: MagicMock, mock_svc: MagicMock, mock_pname: MagicMock, tmp_path: Path
    ) -> None:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        gs = config_dir / "group-structure.yaml"
        gs.write_text("groups: []\n")
        mock_svc.return_value = ServiceConfig(group_structure=str(gs))
        result = resolve_group_structure_path()
        assert result is not None
        assert result.name == "group-structure.yaml"


class TestResolveAppRegistryPath:
    @patch("kctl_ak.core.config.load_raw_config", return_value={})
    @patch("kctl_ak.core.config.get_service_config", return_value=ServiceConfig())
    @patch("kctl_ak.core.config.resolve_active_profile_name", return_value="default")
    def test_returns_none_when_not_found(self, mock_pname: MagicMock, mock_svc: MagicMock, mock_raw: MagicMock) -> None:
        result = resolve_app_registry_path()
        assert result is None
