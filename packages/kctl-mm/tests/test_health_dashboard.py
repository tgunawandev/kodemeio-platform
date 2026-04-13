from __future__ import annotations

from typer.testing import CliRunner

from kctl_mm.commands import dashboard, health


def test_health_status(runner: CliRunner, mock_context) -> None:
    mock_context.client.ping.return_value = {"status": "OK"}
    result = runner.invoke(health.app, ["status"], obj=mock_context)
    assert result.exit_code == 0


def test_health_components(runner, mock_context):
    mock_context.client.ping_full.return_value = {
        "status": "OK",
        "database_status": "OK",
        "filestore_status": "OK",
        "search_status": "OK",
    }
    result = runner.invoke(health.app, ["components"], obj=mock_context)
    assert result.exit_code == 0


def test_dashboard_summary(runner, mock_context):
    mock_context.client.user_stats.return_value = {"total_users_count": 5}
    mock_context.client.list_teams.return_value = [{"id": "t1"}]
    result = runner.invoke(dashboard.app, ["summary"], obj=mock_context)
    assert result.exit_code == 0
