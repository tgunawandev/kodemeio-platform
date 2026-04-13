from kctl_lib.ssh import SSHResult

from kctl_mm.commands.users import app


def test_users_list(runner, mock_context):
    mock_context.client.list_users.return_value = [{"id": "u1", "username": "admin"}]
    result = runner.invoke(app, ["list"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.client.list_users.assert_called_once()


def test_users_get(runner, mock_context):
    mock_context.client.get_user_by_username.return_value = {"id": "u1"}
    assert runner.invoke(app, ["get", "admin"], obj=mock_context).exit_code == 0


def test_users_promote(runner, mock_context):
    mock_context.mm_exec.mmctl.return_value = SSHResult(returncode=0, stdout="ok", stderr="")
    result = runner.invoke(app, ["promote", "admin"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.mm_exec.mmctl.assert_called_once_with(["user", "roles", "system_admin", "admin"])


def test_users_activate_looks_up_id(runner, mock_context):
    mock_context.client.get_user_by_username.return_value = {"id": "u1"}
    mock_context.client.update_user_active.return_value = {"status": "OK"}
    result = runner.invoke(app, ["activate", "admin"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.client.update_user_active.assert_called_once_with("u1", True)
