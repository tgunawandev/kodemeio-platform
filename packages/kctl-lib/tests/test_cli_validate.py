"""Tests for `kctl-profiles validate`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel
from typer.testing import CliRunner


def _write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, data: dict) -> None:
    f = tmp_path / "config.yaml"
    f.write_text(yaml.dump(data))
    monkeypatch.setattr("kctl_lib.config.CONFIG_FILE", f, raising=False)
    monkeypatch.setattr("kctl_lib.config.CONFIG_DIR", tmp_path, raising=False)


class TestValidate:
    def test_passes_valid_profile(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_lib.schemas import register_service_schema

        class _Odoo(BaseModel):
            url: str
            database: str
            api_key: str

        register_service_schema("odoo", _Odoo)

        _write(
            tmp_path,
            monkeypatch,
            {"profiles": {"p": {"odoo": {"url": "u", "database": "d", "api_key": "k"}}}},
        )

        from kctl_lib.cli.main import app

        result = CliRunner().invoke(app, ["validate"])
        assert result.exit_code == 0, result.output
        assert "OK" in result.output or "valid" in result.output.lower()

    def test_reports_missing_required(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_lib.schemas import register_service_schema

        class _Odoo(BaseModel):
            url: str
            database: str
            api_key: str

        register_service_schema("odoo", _Odoo)

        _write(
            tmp_path,
            monkeypatch,
            {"profiles": {"p": {"odoo": {"url": "u"}}}},
        )

        from kctl_lib.cli.main import app

        result = CliRunner().invoke(app, ["validate"])
        assert result.exit_code != 0, result.output
        assert "database" in result.output
        assert "api_key" in result.output

    def test_reports_unknown_field_when_schema_forbids(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_lib.schemas import register_service_schema

        class _Odoo(BaseModel):
            url: str
            database: str
            api_key: str

            model_config = {"extra": "forbid"}

        register_service_schema("odoo", _Odoo)

        _write(
            tmp_path,
            monkeypatch,
            {
                "profiles": {
                    "p": {
                        "odoo": {
                            "url": "u",
                            "database": "d",
                            "api_key": "k",
                            "unknown_field": "x",
                        }
                    }
                }
            },
        )

        from kctl_lib.cli.main import app

        result = CliRunner().invoke(app, ["validate"])
        assert "unknown_field" in result.output
