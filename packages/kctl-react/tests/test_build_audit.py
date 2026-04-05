"""Tests for kctl-react build, audit, and env commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_react.cli import app

runner = CliRunner()


def _extract_json(output: str) -> Any:
    """Extract JSON from output that may mix INFO lines with JSON."""
    for i, ch in enumerate(output):
        if ch in ("[", "{"):
            try:
                return json.loads(output[i:])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"No JSON found in output: {output[:200]}")


class TestBuildHelp:
    def test_build_help(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "build", "--help"])
        assert result.exit_code == 0

    def test_build_size_help(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "build", "size", "--help"])
        assert result.exit_code == 0

    def test_build_history_help(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "build", "history", "--help"])
        assert result.exit_code == 0


class TestBuildSize:
    def test_build_size_no_dist(self, mock_monorepo: Path) -> None:
        """build size reports '--' when no dist dir exists."""
        result = runner.invoke(app, ["--root", str(mock_monorepo), "build", "size"])
        assert result.exit_code == 0

    def test_build_size_with_dist(self, mock_monorepo: Path) -> None:
        """build size reports file size when dist dir exists."""
        sfa_dist = mock_monorepo / "apps" / "sfa" / "dist"
        sfa_dist.mkdir(parents=True, exist_ok=True)
        (sfa_dist / "index.js").write_text("console.log('hello');")
        result = runner.invoke(app, ["--root", str(mock_monorepo), "build", "size"])
        assert result.exit_code == 0

    def test_build_size_json(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "build", "size"])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert isinstance(data, list)
        assert all("app" in d for d in data)


class TestBuildHelpers:
    def test_find_build_dir_returns_none_for_missing(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.build import _find_build_dir

        app_dir = mock_monorepo / "apps" / "sfa"
        assert _find_build_dir(app_dir) is None

    def test_find_build_dir_returns_dist(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.build import _find_build_dir

        app_dir = mock_monorepo / "apps" / "sfa"
        dist = app_dir / "dist"
        dist.mkdir(parents=True, exist_ok=True)
        result = _find_build_dir(app_dir)
        assert result == dist

    def test_format_size_zero(self) -> None:
        from kctl_react.commands.build import _format_size

        assert "--" in _format_size(0)

    def test_format_size_bytes(self) -> None:
        from kctl_react.commands.build import _format_size

        assert "B" in _format_size(100)

    def test_format_size_kb(self) -> None:
        from kctl_react.commands.build import _format_size

        assert "KB" in _format_size(2048)

    def test_format_size_mb(self) -> None:
        from kctl_react.commands.build import _format_size

        assert "MB" in _format_size(2 * 1024 * 1024)

    def test_get_dist_size_missing_dir(self, mock_monorepo: Path) -> None:
        from kctl_react.commands.build import _get_dist_size

        assert _get_dist_size(mock_monorepo / "apps" / "sfa" / "dist") == 0

    def test_get_dist_size_with_files(self, tmp_path: Path) -> None:
        from kctl_react.commands.build import _get_dist_size

        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "a.js").write_bytes(b"x" * 1000)
        (dist / "b.js").write_bytes(b"y" * 500)
        assert _get_dist_size(dist) == 1500


class TestDepsAuditHelp:
    def test_deps_help(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "deps", "--help"])
        assert result.exit_code == 0

    def test_deps_outdated_help(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "deps", "outdated", "--help"])
        assert result.exit_code == 0

    def test_deps_audit_help(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "deps", "audit", "--help"])
        assert result.exit_code == 0


class TestEnvCommands:
    def test_env_show_with_env_file(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "env", "show", "sfa"])
        assert result.exit_code == 0
        assert "VITE_ODOO_URL" in result.output

    def test_env_show_no_env_file(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "env", "show", "lfa"])
        assert result.exit_code == 0

    def test_env_show_invalid_app(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "env", "show", "nonexistent"])
        assert result.exit_code == 1

    def test_env_show_help(self) -> None:
        result = runner.invoke(app, ["env", "show", "--help"])
        assert result.exit_code == 0


class TestLintStrictCheck:
    def test_strict_check(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "lint", "strict-check"])
        assert result.exit_code == 0
        assert "strict" in result.output.lower()

    def test_strict_check_json(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "lint", "strict-check"])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert isinstance(data, list)
        assert all("app" in d and "strict" in d for d in data)

    def test_strict_check_all_apps_strict(self, mock_monorepo: Path) -> None:
        """All mock apps have strict: true — none should report NOT strict."""
        result = runner.invoke(app, ["--root", str(mock_monorepo), "lint", "strict-check"])
        assert result.exit_code == 0
        assert "NOT strict" not in result.output


class TestAppsAdditional:
    def test_apps_list_shows_all_11(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "apps", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 11

    def test_apps_status_invalid(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--root", str(mock_monorepo), "apps", "status", "nonexistent"])
        assert result.exit_code == 1

    def test_apps_ports_json(self, mock_monorepo: Path) -> None:
        result = runner.invoke(app, ["--json", "--root", str(mock_monorepo), "apps", "ports"])
        assert result.exit_code == 0
