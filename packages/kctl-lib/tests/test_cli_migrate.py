"""Tests for `kctl-profiles migrate`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner


class TestMigrateCommand:
    def test_preview_returns_exit_1_with_diff(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        f = tmp_path / "c.yaml"
        f.write_text(
            yaml.dump(
                {
                    "default_profile": "idtpp",
                    "profiles": {"tpp-odoo-erp": {"odoo": {"db": "x"}}},
                }
            )
        )
        from kctl_lib.cli.main import app

        result = CliRunner().invoke(app, ["migrate", "--config", str(f)])
        assert result.exit_code == 1, result.output
        assert "default_profile" in result.output
        assert "tpp-odoo-erp" in result.output
        # File not modified in preview mode.
        assert "tpp-odoo-erp" in f.read_text()

    def test_apply_writes_backup_and_new_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        f = tmp_path / "c.yaml"
        f.write_text(yaml.dump({"profiles": {"tpp-odoo-erp": {"odoo": {"db": "x"}}}}))
        from kctl_lib.cli.main import app

        result = CliRunner().invoke(app, ["migrate", "--config", str(f), "--yes"])
        assert result.exit_code == 0, result.output
        new_data = yaml.safe_load(f.read_text())
        assert "idtpp-tpp-odoo-erp" in new_data["profiles"]
        assert "tpp-odoo-erp" not in new_data["profiles"]
        # Backup exists.
        backups = list(tmp_path.glob("c.yaml.bak.*"))
        assert len(backups) == 1

    def test_no_changes_returns_exit_0(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        f = tmp_path / "c.yaml"
        f.write_text(yaml.dump({"profiles": {"idtpp": {}}}))
        from kctl_lib.cli.main import app

        result = CliRunner().invoke(app, ["migrate", "--config", str(f)])
        assert result.exit_code == 0, result.output
        assert "already migrated" in result.output

    def test_missing_file_errors(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_lib.cli.main import app

        result = CliRunner().invoke(app, ["migrate", "--config", str(tmp_path / "does-not-exist.yaml")])
        assert result.exit_code == 2
        assert "not found" in result.output.lower()
