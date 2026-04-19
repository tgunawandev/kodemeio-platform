"""Tests for `kctl-profiles current`."""

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


class TestCurrentCommand:
    def test_reports_env_var_source(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write(tmp_path, monkeypatch, {"profiles": {"idtpp": {}}})
        monkeypatch.setenv("KCTL_PROFILES_PROFILE", "idtpp")
        from kctl_lib.cli.main import app

        result = CliRunner().invoke(app, ["current"])
        assert result.exit_code == 0, result.output
        assert "idtpp" in result.output
        assert "KCTL_PROFILES_PROFILE" in result.output

    def test_reports_flag_source(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write(tmp_path, monkeypatch, {"profiles": {"idtpp": {}}})
        monkeypatch.delenv("KCTL_PROFILES_PROFILE", raising=False)
        from kctl_lib.cli.main import app

        result = CliRunner().invoke(app, ["current", "--profile", "idtpp"])
        assert result.exit_code == 0
        assert "idtpp" in result.output
        assert "--profile" in result.output or "flag" in result.output.lower()

    def test_errors_when_unset(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write(tmp_path, monkeypatch, {"profiles": {"idtpp": {}}})
        monkeypatch.delenv("KCTL_PROFILES_PROFILE", raising=False)
        from kctl_lib.cli.main import app

        result = CliRunner().invoke(app, ["current"])
        assert result.exit_code != 0
        # The error message from resolve_active_profile_name includes this text.
        assert "No profile" in result.output
