from typer.testing import CliRunner

from kctl_mm.commands import completions, self_update, skill_cmd


def test_self_update_help(runner: CliRunner) -> None:
    assert runner.invoke(self_update.app, ["--help"]).exit_code == 0


def test_completions_help(runner: CliRunner) -> None:
    assert runner.invoke(completions.app, ["--help"]).exit_code == 0


def test_skill_help(runner: CliRunner) -> None:
    assert runner.invoke(skill_cmd.app, ["--help"]).exit_code == 0
