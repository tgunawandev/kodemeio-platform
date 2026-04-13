from kctl_lib.ssh import SSHResult

from kctl_mm.commands.teams import app


def test_teams_list(runner, mock_context):
    mock_context.client.list_teams.return_value = [{"id": "t1", "name": "core"}]
    result = runner.invoke(app, ["list"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.client.list_teams.assert_called_once()


def test_teams_create(runner, mock_context):
    mock_context.client.create_team.return_value = {"id": "t1"}
    result = runner.invoke(app, ["create", "core", "Core"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.client.create_team.assert_called_once_with("core", "Core")


def test_teams_add_mmctl(runner, mock_context):
    mock_context.mm_exec.mmctl.return_value = SSHResult(returncode=0, stdout="ok", stderr="")
    result = runner.invoke(app, ["add", "core", "admin"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.mm_exec.mmctl.assert_called_once_with(["team", "users", "add", "core", "admin"])


def test_teams_members_lookup(runner, mock_context):
    mock_context.client.get_team_by_name.return_value = {"id": "t1"}
    mock_context.client.list_team_members.return_value = []
    result = runner.invoke(app, ["members", "core"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.client.list_team_members.assert_called_once_with("t1")
