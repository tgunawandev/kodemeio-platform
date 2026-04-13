from kctl_lib.ssh import SSHResult

from kctl_mm.commands.integrations import app


def test_integrations_oauth_list(runner, mock_context):
    mock_context.mm_exec.mmctl_json.return_value = [{"id": "o1"}]
    result = runner.invoke(app, ["oauth-list"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.mm_exec.mmctl_json.assert_called_once_with(["oauth", "list-apps"])


def test_integrations_ldap_sync(runner, mock_context):
    mock_context.mm_exec.mmctl.return_value = SSHResult(returncode=0, stdout="synced", stderr="")
    result = runner.invoke(app, ["ldap-sync"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.mm_exec.mmctl.assert_called_once_with(["ldap", "sync"])
