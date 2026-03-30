from typer.testing import CliRunner

from kctl_telegram.cli import app

runner = CliRunner()


class TestCLISmoke:
    def test_help_exits_zero(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
