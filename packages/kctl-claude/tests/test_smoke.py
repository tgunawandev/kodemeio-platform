"""Smoke tests for kctl-claude CLI — verify all commands are wired up."""

from typer.testing import CliRunner

from kctl_claude.cli import app

runner = CliRunner()


class TestCLISmoke:
    def test_help_exits_zero(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_config_help(self) -> None:
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0

    def test_status_help(self) -> None:
        result = runner.invoke(app, ["status", "--help"])
        assert result.exit_code == 0

    def test_sync_help(self) -> None:
        result = runner.invoke(app, ["sync", "--help"])
        assert result.exit_code == 0

    def test_verify_help(self) -> None:
        result = runner.invoke(app, ["verify", "--help"])
        assert result.exit_code == 0

    def test_api_help(self) -> None:
        result = runner.invoke(app, ["api", "--help"])
        assert result.exit_code == 0

    def test_env_help(self) -> None:
        result = runner.invoke(app, ["env", "--help"])
        assert result.exit_code == 0

    def test_backup_help(self) -> None:
        result = runner.invoke(app, ["backup", "--help"])
        assert result.exit_code == 0

    def test_setup_help(self) -> None:
        result = runner.invoke(app, ["setup", "--help"])
        assert result.exit_code == 0

    def test_doctor_help(self) -> None:
        result = runner.invoke(app, ["doctor", "--help"])
        assert result.exit_code == 0

    def test_completions_help(self) -> None:
        result = runner.invoke(app, ["completions", "--help"])
        assert result.exit_code == 0

    def test_update_help(self) -> None:
        result = runner.invoke(app, ["update", "--help"])
        assert result.exit_code == 0

    def test_verbose_flag(self) -> None:
        result = runner.invoke(app, ["--verbose", "--help"])
        assert result.exit_code == 0

    def test_json_flag(self) -> None:
        result = runner.invoke(app, ["--json", "--help"])
        assert result.exit_code == 0

    def test_quiet_flag(self) -> None:
        result = runner.invoke(app, ["-q", "--help"])
        assert result.exit_code == 0

    def test_no_command_shows_help(self) -> None:
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "kctl-claude" in result.output.lower() or "Usage" in result.output
