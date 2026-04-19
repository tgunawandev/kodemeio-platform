"""Tests for `kctl-profiles list`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner


def _write_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, data: dict) -> None:
    f = tmp_path / "config.yaml"
    f.write_text(yaml.dump(data))
    monkeypatch.setattr("kctl_lib.config.CONFIG_FILE", f, raising=False)
    monkeypatch.setattr("kctl_lib.config.CONFIG_DIR", tmp_path, raising=False)


class TestListCommand:
    def test_lists_profiles_with_services(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_config(
            tmp_path,
            monkeypatch,
            {
                "profiles": {
                    "idtpp": {"dokploy": {"url": "x"}, "postgres": {"host": "y"}},
                    "idtpp-tpp-odoo-erp": {"odoo": {"url": "z"}},
                }
            },
        )
        from kctl_lib.cli.main import app

        result = CliRunner().invoke(app, ["list"])
        assert result.exit_code == 0, result.output
        assert "idtpp" in result.output
        assert "idtpp-tpp-odoo-erp" in result.output
        assert "dokploy" in result.output
        assert "postgres" in result.output
        assert "odoo" in result.output

    def test_empty_config_message(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_config(tmp_path, monkeypatch, {})
        from kctl_lib.cli.main import app

        result = CliRunner().invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No profiles" in result.output or "no profiles" in result.output.lower()
