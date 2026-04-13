from kctl_mm.commands.bots import app


def test_bots_list(runner, mock_context):
    mock_context.client.list_bots.return_value = [{"user_id": "b1", "username": "bot"}]
    result = runner.invoke(app, ["list"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.client.list_bots.assert_called_once()


def test_bots_enable(runner, mock_context):
    mock_context.client.enable_bot.return_value = {"status": "OK"}
    result = runner.invoke(app, ["enable", "b1"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.client.enable_bot.assert_called_once_with("b1")
