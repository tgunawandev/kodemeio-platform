from kctl_mm.commands.webhooks import app


def test_webhooks_list_incoming(runner, mock_context):
    mock_context.client.list_incoming_hooks.return_value = [{"id": "h1"}]
    result = runner.invoke(app, ["list-incoming"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.client.list_incoming_hooks.assert_called_once()


def test_webhooks_create_incoming(runner, mock_context):
    mock_context.client.create_incoming_hook.return_value = {"id": "h1"}
    result = runner.invoke(app, ["create-incoming", "c1", "Alerts"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.client.create_incoming_hook.assert_called_once_with("c1", "Alerts")
