"""Prefix-inheritance chain resolver (Stage B)."""

from __future__ import annotations


class TestInheritanceChain:
    def test_single_segment_returns_just_self(self) -> None:
        from kctl_lib.config import resolve_inheritance_chain

        assert resolve_inheritance_chain("idtpp") == ["idtpp"]

    def test_multi_segment_walks_back(self) -> None:
        from kctl_lib.config import resolve_inheritance_chain

        assert resolve_inheritance_chain("idtpp-tpp-odoo-erp") == [
            "idtpp-tpp-odoo-erp",
            "idtpp-tpp-odoo",
            "idtpp-tpp",
            "idtpp",
        ]

    def test_staging_suffix_walks_back(self) -> None:
        from kctl_lib.config import resolve_inheritance_chain

        assert resolve_inheritance_chain("idtpp-tpp-odoo-erp-stg") == [
            "idtpp-tpp-odoo-erp-stg",
            "idtpp-tpp-odoo-erp",
            "idtpp-tpp-odoo",
            "idtpp-tpp",
            "idtpp",
        ]

    def test_empty_profile_name_raises(self) -> None:
        from kctl_lib.config import resolve_inheritance_chain

        try:
            resolve_inheritance_chain("")
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError on empty profile name")


from pathlib import Path
from typing import Any

import pytest


class TestGetServiceConfigInheritance:
    def _write_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import yaml

        config_file = tmp_path / "config.yaml"
        monkeypatch.setattr("kctl_lib.config.CONFIG_FILE", config_file)
        monkeypatch.setattr("kctl_lib.config.CONFIG_DIR", tmp_path)
        data: dict[str, Any] = {
            "profiles": {
                "idtpp": {
                    "dokploy": {"url": "https://dokploy.idtpp.com"},
                    "postgres": {"host": "10.0.0.2"},
                },
                "idtpp-tpp-odoo-erp": {"odoo": {"url": "https://tpp-odoo-erp.idtpp.com"}},
            }
        }
        config_file.write_text(yaml.dump(data))

    def test_app_profile_inherits_platform_service(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._write_config(tmp_path, monkeypatch)
        from kctl_lib.config import get_service_config

        # idtpp-tpp-odoo-erp has no postgres; should inherit from idtpp.
        pg = get_service_config("idtpp-tpp-odoo-erp", "postgres")
        assert pg == {"host": "10.0.0.2"}

    def test_app_profile_uses_own_service_over_parent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._write_config(tmp_path, monkeypatch)
        from kctl_lib.config import get_service_config

        # idtpp-tpp-odoo-erp has its own odoo; must NOT inherit.
        odoo = get_service_config("idtpp-tpp-odoo-erp", "odoo")
        assert odoo == {"url": "https://tpp-odoo-erp.idtpp.com"}

    def test_missing_service_returns_empty_dict(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._write_config(tmp_path, monkeypatch)
        from kctl_lib.config import get_service_config

        assert get_service_config("idtpp-tpp-odoo-erp", "nonexistent") == {}

    def test_nonexistent_profile_returns_empty_dict(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._write_config(tmp_path, monkeypatch)
        from kctl_lib.config import get_service_config

        # No leaf, but `idtpp` in chain has dokploy — current behavior: do NOT
        # resolve from chain if leaf doesn't exist (explicit-profile safety).
        # This test asserts the explicit-safety behavior.
        assert get_service_config("does-not-exist-at-all", "dokploy") == {}
