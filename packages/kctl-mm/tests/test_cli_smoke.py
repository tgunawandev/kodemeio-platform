from typer.testing import CliRunner
from kctl_mm.cli import app


def test_top_level_help_lists_all_groups(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    expected = [
        "config",
        "doctor",
        "self-update",
        "completions",
        "skill",
        "status",
        "logs",
        "deploy",
        "health",
        "dashboard",
        "users",
        "teams",
        "channels",
        "permissions",
        "posts",
        "mm-config",
        "maintenance",
        "webhooks",
        "bots",
        "plugins",
        "integrations",
        "jobs",
        "audit",
        "import-export",
    ]
    for group in expected:
        assert group in result.stdout, f"group {group!r} missing"


def test_version(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "kctl-mm" in result.stdout
