from kctl_lib.ssh import SSHResult

from kctl_mm.commands.channels import app


def test_channels_list(runner, mock_context):
    mock_context.client.get_team_by_name.return_value = {"id": "t1"}
    mock_context.client.list_channels_for_team.return_value = [{"id": "c1", "name": "town"}]
    result = runner.invoke(app, ["list", "core"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.client.list_channels_for_team.assert_called_once_with("t1")


def test_channels_create(runner, mock_context):
    mock_context.client.get_team_by_name.return_value = {"id": "t1"}
    mock_context.client.create_channel.return_value = {"id": "c1"}
    result = runner.invoke(app, ["create", "core", "town", "Town Square"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.client.create_channel.assert_called_once_with("t1", "town", "Town Square", private=False)


def test_channels_add(runner, mock_context):
    mock_context.mm_exec.mmctl.return_value = SSHResult(returncode=0, stdout="ok", stderr="")
    result = runner.invoke(app, ["add", "core", "town", "admin"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.mm_exec.mmctl.assert_called_once_with(["channel", "users", "add", "core:town", "admin"])
