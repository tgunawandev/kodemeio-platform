"""CLI smoke tests for kctl-supa."""

from typer.testing import CliRunner
from kctl_supa.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "kctl-supa" in result.output


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Kodemeio Supabase CLI" in result.output


def test_config_help():
    result = runner.invoke(app, ["config", "--help"])
    assert result.exit_code == 0


def test_cron_help():
    result = runner.invoke(app, ["cron", "--help"])
    assert result.exit_code == 0
    assert "cron" in result.output.lower()


def test_vault_help():
    result = runner.invoke(app, ["vault", "--help"])
    assert result.exit_code == 0
    assert "vault" in result.output.lower() or "secret" in result.output.lower()


def test_queues_help():
    result = runner.invoke(app, ["queues", "--help"])
    assert result.exit_code == 0
    assert "queue" in result.output.lower()


def test_advisors_help():
    result = runner.invoke(app, ["advisors", "--help"])
    assert result.exit_code == 0
    assert "advisor" in result.output.lower() or "security" in result.output.lower()


def test_publications_help():
    result = runner.invoke(app, ["publications", "--help"])
    assert result.exit_code == 0
    assert "publication" in result.output.lower()


def test_integrations_help():
    result = runner.invoke(app, ["integrations", "--help"])
    assert result.exit_code == 0
    assert "integration" in result.output.lower()


def test_upgrade_help():
    result = runner.invoke(app, ["upgrade", "--help"])
    assert result.exit_code == 0
    assert "upgrade" in result.output.lower()


def test_settings_help():
    result = runner.invoke(app, ["settings", "--help"])
    assert result.exit_code == 0
    assert "setting" in result.output.lower()


def test_db_has_new_subcommands():
    result = runner.invoke(app, ["db", "--help"])
    assert result.exit_code == 0
    for cmd in [
        "functions",
        "triggers",
        "enums",
        "indexes",
        "columns",
        "roles",
        "publications",
        "wrappers",
        "webhooks",
    ]:
        assert cmd in result.output.lower(), f"Missing db subcommand: {cmd}"


def test_auth_has_new_subcommands():
    result = runner.invoke(app, ["auth", "--help"])
    assert result.exit_code == 0
    assert "providers" in result.output.lower()
    assert "policies" in result.output.lower()


def test_storage_has_new_subcommands():
    result = runner.invoke(app, ["storage", "--help"])
    assert result.exit_code == 0
    assert "policies" in result.output.lower()
    assert "upload" in result.output.lower()
    assert "download" in result.output.lower()


def test_functions_has_secrets():
    result = runner.invoke(app, ["functions", "--help"])
    assert result.exit_code == 0
    assert "secrets" in result.output.lower()
