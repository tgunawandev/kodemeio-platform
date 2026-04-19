"""Tests for `kctl-profiles show`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner


def _write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, data: dict) -> None:
    f = tmp_path / "config.yaml"
    f.write_text(yaml.dump(data))
    monkeypatch.setattr("kctl_lib.config.CONFIG_FILE", f, raising=False)
    monkeypatch.setattr("kctl_lib.config.CONFIG_DIR", tmp_path, raising=False)


class TestShowCommand:
    def test_shows_resolved_services_for_app_profile(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write(
            tmp_path,
            monkeypatch,
            {
                "profiles": {
                    "idtpp": {
                        "dokploy": {"url": "https://dokploy.idtpp.com"},
                        "postgres": {"host": "10.0.0.2"},
                    },
                    "idtpp-tpp-odoo-erp": {
                        "odoo": {
                            "url": "https://tpp-odoo-erp.idtpp.com",
                            "api_key": "secret-1989Bisnis1",
                        }
                    },
                }
            },
        )
        from kctl_lib.cli.main import app

        result = CliRunner().invoke(app, ["show", "idtpp-tpp-odoo-erp"])
        assert result.exit_code == 0, result.output
        # Services resolved via inheritance:
        assert "dokploy" in result.output
        assert "postgres" in result.output
        assert "odoo" in result.output
        # Secret is masked:
        assert "secret-1989Bisnis1" not in result.output
        assert "****" in result.output

    def test_show_reveal_flag_unmasks(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write(
            tmp_path,
            monkeypatch,
            {
                "profiles": {
                    "p": {
                        "odoo": {
                            "url": "https://x.com",
                            "api_key": "supersecretvaluehere",
                        }
                    }
                }
            },
        )
        from kctl_lib.cli.main import app

        result = CliRunner().invoke(app, ["show", "p", "--reveal"])
        assert result.exit_code == 0
        assert "supersecretvaluehere" in result.output

    def test_show_unknown_profile_errors(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write(tmp_path, monkeypatch, {"profiles": {"idtpp": {}}})
        from kctl_lib.cli.main import app

        result = CliRunner().invoke(app, ["show", "does-not-exist"])
        assert result.exit_code != 0
        assert "does-not-exist" in result.output
