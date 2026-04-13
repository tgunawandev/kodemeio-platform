from kctl_lib.ssh import SSHResult

from kctl_mm.commands.permissions import WELL_KNOWN_ROLES, app


def test_permissions_list(runner, mock_context):
    result = runner.invoke(app, ["list"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.output.raw_json.assert_called_once_with(WELL_KNOWN_ROLES)


def test_permissions_add(runner, mock_context):
    mock_context.mm_exec.mmctl.return_value = SSHResult(returncode=0, stdout="ok", stderr="")
    result = runner.invoke(app, ["add", "system_admin", "manage_system"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.mm_exec.mmctl.assert_called_once_with(["permissions", "add", "system_admin", "manage_system"])


def test_permissions_assign(runner, mock_context):
    mock_context.mm_exec.mmctl.return_value = SSHResult(returncode=0, stdout="assigned", stderr="")
    result = runner.invoke(app, ["assign", "system_admin", "alice"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.mm_exec.mmctl.assert_called_once_with(["permissions", "role-assign", "system_admin", "alice"])
