from typer.testing import CliRunner

from kctl_mm.commands.config_cmd import app


def test_config_help(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for sub in ("init", "add", "use", "show", "validate", "remove", "set", "profiles", "current"):
        assert sub in result.stdout
