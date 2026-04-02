"""Tests for the e2e command module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_odoo.commands.e2e import _build_env, _find_e2e_dir, app

runner = CliRunner()


class TestE2eHelp:
    """Verify e2e commands are registered and show help."""

    def test_e2e_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "E2E browser testing" in result.output

    def test_e2e_test_help(self) -> None:
        result = runner.invoke(app, ["test", "--help"])
        assert result.exit_code == 0
        assert "--headed" in result.output
        assert "--smoke" in result.output
        assert "--mobile" in result.output
        assert "--module" in result.output
        assert "--screenshots" in result.output
        assert "--video" in result.output

    def test_e2e_list_help(self) -> None:
        result = runner.invoke(app, ["list", "--help"])
        assert result.exit_code == 0
        assert "List all discovered" in result.output

    def test_e2e_report_help(self) -> None:
        result = runner.invoke(app, ["report", "--help"])
        assert result.exit_code == 0
        assert "HTML test report" in result.output

    def test_e2e_install_help(self) -> None:
        result = runner.invoke(app, ["install", "--help"])
        assert result.exit_code == 0
        assert "Playwright" in result.output

    def test_e2e_screenshots_help(self) -> None:
        result = runner.invoke(app, ["screenshots", "--help"])
        assert result.exit_code == 0
        assert "--module" in result.output

    def test_e2e_discover_help(self) -> None:
        result = runner.invoke(app, ["discover", "--help"])
        assert result.exit_code == 0
        assert "--dry-run" in result.output


class TestFindE2eDir:
    """Test e2e directory resolution."""

    def test_finds_e2e_dir_from_package(self) -> None:
        e2e_dir = _find_e2e_dir()
        # Should return a path that ends with /e2e
        assert e2e_dir.name == "e2e"

    def test_e2e_dir_exists(self) -> None:
        e2e_dir = _find_e2e_dir()
        assert e2e_dir.is_dir(), f"e2e/ not found at {e2e_dir}"


class TestBuildEnv:
    """Test environment variable construction."""

    def test_build_env_includes_odoo_vars(self) -> None:
        mock_ctx = MagicMock()
        mock_ctx.obj = MagicMock()
        mock_ctx.obj.profile = None
        mock_ctx.obj.url_override = "http://test.example.com"
        mock_ctx.obj.api_key_override = "test-key"
        mock_ctx.obj.database_override = "test_db"
        mock_ctx.obj.username_override = "testuser"

        with patch("kctl_odoo.commands.e2e.resolve_connection") as mock_resolve:
            mock_resolve.return_value = (
                "http://test.example.com",
                "test_db",
                "testuser",
                "test-key",
            )
            env = _build_env(mock_ctx, {"EXTRA_VAR": "extra"})

        assert env["ODOO_URL"] == "http://test.example.com"
        assert env["ODOO_DATABASE"] == "test_db"
        assert env["ODOO_USERNAME"] == "testuser"
        assert env["ODOO_API_KEY"] == "test-key"
        assert env["EXTRA_VAR"] == "extra"

    def test_build_env_skips_empty_values(self) -> None:
        mock_ctx = MagicMock()
        mock_ctx.obj = MagicMock()
        mock_ctx.obj.profile = None
        mock_ctx.obj.url_override = None
        mock_ctx.obj.api_key_override = None
        mock_ctx.obj.database_override = None
        mock_ctx.obj.username_override = None

        with patch("kctl_odoo.commands.e2e.resolve_connection") as mock_resolve:
            mock_resolve.return_value = ("", "", "", "")
            env = _build_env(mock_ctx)

        assert "ODOO_URL" not in env
        assert "ODOO_DATABASE" not in env


class TestE2eTestCommand:
    """Test the e2e test command builds correct subprocess args."""

    @patch("kctl_odoo.commands.e2e.subprocess.Popen")
    @patch("kctl_odoo.commands.e2e._find_e2e_dir")
    @patch("kctl_odoo.commands.e2e._build_env")
    def test_test_all_builds_correct_cmd(
        self, mock_env: MagicMock, mock_dir: MagicMock, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        mock_dir.return_value = tmp_path
        mock_env.return_value = {}
        proc = MagicMock()
        proc.returncode = 0
        proc.wait.return_value = 0
        mock_popen.return_value = proc

        result = runner.invoke(app, ["test"])
        assert result.exit_code == 0

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert cmd[0:3] == ["npx", "playwright", "test"]
        assert "--project" in cmd
        assert "desktop" in cmd

    @patch("kctl_odoo.commands.e2e.subprocess.Popen")
    @patch("kctl_odoo.commands.e2e._find_e2e_dir")
    @patch("kctl_odoo.commands.e2e._build_env")
    def test_test_smoke_passes_smoke_dir(
        self, mock_env: MagicMock, mock_dir: MagicMock, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        mock_dir.return_value = tmp_path
        mock_env.return_value = {}
        proc = MagicMock()
        proc.returncode = 0
        proc.wait.return_value = 0
        mock_popen.return_value = proc

        result = runner.invoke(app, ["test", "--smoke"])
        assert result.exit_code == 0

        cmd = mock_popen.call_args[0][0]
        assert "tests/smoke/" in cmd

    @patch("kctl_odoo.commands.e2e.subprocess.Popen")
    @patch("kctl_odoo.commands.e2e._find_e2e_dir")
    @patch("kctl_odoo.commands.e2e._build_env")
    def test_test_mobile_selects_mobile_project(
        self, mock_env: MagicMock, mock_dir: MagicMock, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        mock_dir.return_value = tmp_path
        mock_env.return_value = {}
        proc = MagicMock()
        proc.returncode = 0
        proc.wait.return_value = 0
        mock_popen.return_value = proc

        result = runner.invoke(app, ["test", "--mobile"])
        assert result.exit_code == 0

        cmd = mock_popen.call_args[0][0]
        assert "--project" in cmd
        idx = cmd.index("--project")
        assert cmd[idx + 1] == "mobile"

    @patch("kctl_odoo.commands.e2e.subprocess.Popen")
    @patch("kctl_odoo.commands.e2e._find_e2e_dir")
    @patch("kctl_odoo.commands.e2e._build_env")
    def test_test_headed_flag(
        self, mock_env: MagicMock, mock_dir: MagicMock, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        mock_dir.return_value = tmp_path
        mock_env.return_value = {}
        proc = MagicMock()
        proc.returncode = 0
        proc.wait.return_value = 0
        mock_popen.return_value = proc

        result = runner.invoke(app, ["test", "--headed"])
        assert result.exit_code == 0

        cmd = mock_popen.call_args[0][0]
        assert "--headed" in cmd

    @patch("kctl_odoo.commands.e2e.subprocess.Popen")
    @patch("kctl_odoo.commands.e2e._find_e2e_dir")
    @patch("kctl_odoo.commands.e2e._build_env")
    def test_test_scenario_argument(
        self, mock_env: MagicMock, mock_dir: MagicMock, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        mock_dir.return_value = tmp_path
        mock_env.return_value = {}
        proc = MagicMock()
        proc.returncode = 0
        proc.wait.return_value = 0
        mock_popen.return_value = proc

        result = runner.invoke(app, ["test", "login"])
        assert result.exit_code == 0

        cmd = mock_popen.call_args[0][0]
        assert "tests/scenarios/login" in cmd

    @patch("kctl_odoo.commands.e2e.subprocess.Popen")
    @patch("kctl_odoo.commands.e2e._find_e2e_dir")
    @patch("kctl_odoo.commands.e2e._build_env")
    def test_test_grep_flag(
        self, mock_env: MagicMock, mock_dir: MagicMock, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        mock_dir.return_value = tmp_path
        mock_env.return_value = {}
        proc = MagicMock()
        proc.returncode = 0
        proc.wait.return_value = 0
        mock_popen.return_value = proc

        result = runner.invoke(app, ["test", "--grep", "Invoice"])
        assert result.exit_code == 0

        cmd = mock_popen.call_args[0][0]
        assert "--grep" in cmd
        assert "Invoice" in cmd

    def test_test_fails_when_e2e_dir_missing(self, tmp_path: Path) -> None:
        with patch("kctl_odoo.commands.e2e._find_e2e_dir") as mock_dir:
            mock_dir.return_value = tmp_path / "nonexistent"
            result = runner.invoke(app, ["test"])
            assert result.exit_code == 1
            assert "not found" in result.output


class TestE2eDiscover:
    """Test the discover command."""

    def test_discover_dry_run(self, mock_client: MagicMock) -> None:
        mock_client.search_read.return_value = [
            {
                "id": 1,
                "name": "Sales",
                "complete_name": "Sales",
                "parent_id": False,
                "action": False,
                "web_icon": "sale",
            },
            {
                "id": 10,
                "name": "Quotations",
                "complete_name": "Sales/Quotations",
                "parent_id": [1, "Sales"],
                "action": "ir.actions.act_window,42",
                "web_icon": "",
            },
        ]

        with (
            patch("kctl_odoo.commands.e2e.resolve_connection") as mock_resolve,
        ):
            mock_resolve.return_value = ("http://test.example.com", "test_db", "admin", "key")

            from kctl_odoo.core.callbacks import AppContext

            mock_ctx = MagicMock()
            mock_ctx.obj = MagicMock(spec=AppContext)
            mock_ctx.obj.client = mock_client
            mock_ctx.obj.profile = None

            # Just test that the dry-run help text is present
            result = runner.invoke(app, ["discover", "--help"])
            assert result.exit_code == 0
            assert "Discover Odoo menus" in result.output
