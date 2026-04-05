"""Tests for kctl-api apps commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from kctl_api.cli import app
from kctl_api.core.utils import KNOWN_APPS

runner = CliRunner()


# ---------------------------------------------------------------------------
# apps list
# ---------------------------------------------------------------------------
class TestAppsList:
    def test_list_exits_ok(self) -> None:
        result = runner.invoke(app, ["apps", "list"])
        assert result.exit_code == 0

    def test_list_shows_api_main(self) -> None:
        result = runner.invoke(app, ["apps", "list"])
        assert "api-main" in result.output

    def test_list_shows_ai_main(self) -> None:
        result = runner.invoke(app, ["apps", "list"])
        assert "ai-main" in result.output

    def test_list_shows_all_known_apps(self) -> None:
        result = runner.invoke(app, ["apps", "list"])
        for name in KNOWN_APPS:
            assert name in result.output, f"App '{name}' not in list output"

    def test_list_json_output(self) -> None:
        result = runner.invoke(app, ["--json", "apps", "list"])
        assert result.exit_code == 0
        assert '"name": "api-main"' in result.output

    def test_list_json_contains_type(self) -> None:
        result = runner.invoke(app, ["--json", "apps", "list"])
        assert '"type"' in result.output

    def test_list_json_contains_port(self) -> None:
        result = runner.invoke(app, ["--json", "apps", "list"])
        assert '"port"' in result.output

    def test_list_json_contains_module(self) -> None:
        result = runner.invoke(app, ["--json", "apps", "list"])
        assert '"module"' in result.output

    def test_list_shows_port_8000(self) -> None:
        result = runner.invoke(app, ["apps", "list"])
        assert "8000" in result.output

    def test_list_shows_api_type(self) -> None:
        result = runner.invoke(app, ["apps", "list"])
        assert "API" in result.output


# ---------------------------------------------------------------------------
# apps info
# ---------------------------------------------------------------------------
class TestAppsInfo:
    def test_info_known_app(self) -> None:
        result = runner.invoke(app, ["apps", "info", "api-main"])
        assert result.exit_code == 0
        assert "api-main" in result.output

    def test_info_shows_port(self) -> None:
        result = runner.invoke(app, ["apps", "info", "api-main"])
        assert "8000" in result.output

    def test_info_shows_module(self) -> None:
        result = runner.invoke(app, ["apps", "info", "api-main"])
        assert "kodemeio_api_main" in result.output

    def test_info_ai_main(self) -> None:
        result = runner.invoke(app, ["apps", "info", "ai-main"])
        assert result.exit_code == 0
        assert "8010" in result.output

    def test_info_unknown_app_exits_1(self) -> None:
        result = runner.invoke(app, ["apps", "info", "nonexistent-app"])
        assert result.exit_code == 1

    def test_info_unknown_app_error_message(self) -> None:
        result = runner.invoke(app, ["apps", "info", "nonexistent-app"])
        assert "Unknown app" in result.output or "nonexistent-app" in result.output

    def test_info_json_mode(self) -> None:
        result = runner.invoke(app, ["--json", "apps", "info", "api-main"])
        assert result.exit_code == 0
        assert '"name": "api-main"' in result.output

    def test_info_all_apps_work(self) -> None:
        """Verify info works for every known app."""
        for name in KNOWN_APPS:
            result = runner.invoke(app, ["apps", "info", name])
            assert result.exit_code == 0, f"apps info {name} failed: {result.output}"


# ---------------------------------------------------------------------------
# apps env
# ---------------------------------------------------------------------------
class TestAppsEnv:
    def test_env_unknown_app_exits_1(self) -> None:
        result = runner.invoke(app, ["apps", "env", "nonexistent"])
        assert result.exit_code == 1

    def test_env_known_app_no_env_file(self, tmp_path: Path) -> None:
        """When project root has no .env.example, should print info and return 0."""
        with patch("kctl_api.commands.apps.find_project_root", return_value=tmp_path):
            result = runner.invoke(app, ["apps", "env", "api-main"])
        assert result.exit_code == 0

    def test_env_known_app_with_env_file(self, tmp_path: Path) -> None:
        env_example = tmp_path / ".env.example"
        env_example.write_text("DATABASE_URL=postgresql://localhost/mydb\nSECRET_KEY=changeme\n")
        with patch("kctl_api.commands.apps.find_project_root", return_value=tmp_path):
            result = runner.invoke(app, ["apps", "env", "api-main"])
        assert result.exit_code == 0
        assert "DATABASE_URL" in result.output


# ---------------------------------------------------------------------------
# apps deps
# ---------------------------------------------------------------------------
class TestAppsDeps:
    def test_deps_unknown_app_exits_1(self) -> None:
        result = runner.invoke(app, ["apps", "deps", "nonexistent"])
        assert result.exit_code == 1

    def test_deps_no_pyproject(self, tmp_path: Path) -> None:
        with patch("kctl_api.commands.apps.find_project_root", return_value=tmp_path):
            result = runner.invoke(app, ["apps", "deps", "api-main"])
        assert result.exit_code == 0

    def test_deps_with_pyproject(self, tmp_path: Path) -> None:
        app_dir = tmp_path / "apps" / "api-main"
        app_dir.mkdir(parents=True)
        pyproject = app_dir / "pyproject.toml"
        pyproject.write_text('[project]\ndependencies = [\n    "fastapi>=0.100",\n    "httpx",\n]\n')
        with patch("kctl_api.commands.apps.find_project_root", return_value=tmp_path):
            result = runner.invoke(app, ["apps", "deps", "api-main"])
        assert result.exit_code == 0
        assert "fastapi" in result.output


# ---------------------------------------------------------------------------
# KNOWN_APPS data integrity
# ---------------------------------------------------------------------------
class TestKnownAppsData:
    def test_known_apps_not_empty(self) -> None:
        assert len(KNOWN_APPS) > 0

    def test_api_main_metadata(self) -> None:
        assert "api-main" in KNOWN_APPS
        meta = KNOWN_APPS["api-main"]
        assert meta["type"] == "API"
        assert meta["port"] == "8000"
        assert meta["module"] == "kodemeio_api_main"

    def test_ai_main_metadata(self) -> None:
        assert "ai-main" in KNOWN_APPS
        meta = KNOWN_APPS["ai-main"]
        assert meta["port"] == "8010"

    def test_all_apps_have_required_keys(self) -> None:
        for name, meta in KNOWN_APPS.items():
            assert "type" in meta, f"App {name} missing 'type'"
            assert "module" in meta, f"App {name} missing 'module'"
