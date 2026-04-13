from kctl_mm.commands.audit import app


def test_audit_login(runner, mock_context):
    mock_context.client.get_user_by_username.return_value = {"id": "u1"}
    mock_context.client.list_user_audits.return_value = [{"action": "login"}]
    result = runner.invoke(app, ["login", "alice"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.client.get_user_by_username.assert_called_once_with("alice")
    mock_context.client.list_user_audits.assert_called_once_with("u1")


def test_audit_security(runner, mock_context):
    mock_context.client.list_compliance_reports.return_value = [{"id": "r1"}]
    result = runner.invoke(app, ["security"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.client.list_compliance_reports.assert_called_once()
