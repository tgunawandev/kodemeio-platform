from kctl_lib.exceptions import NotFoundError

from kctl_mm.commands.posts import app


def test_posts_get(runner, mock_context):
    mock_context.client.get_post.return_value = {"id": "p1", "message": "hi"}
    result = runner.invoke(app, ["get", "p1"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.client.get_post.assert_called_once_with("p1")


def test_posts_get_not_found(runner, mock_context):
    mock_context.client.get_post.side_effect = NotFoundError("post", "p1")
    result = runner.invoke(app, ["get", "p1"], obj=mock_context)
    assert result.exit_code != 0


def test_posts_delete(runner, mock_context):
    mock_context.client.delete_post.return_value = {"status": "OK"}
    result = runner.invoke(app, ["delete", "p1"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.client.delete_post.assert_called_once_with("p1")
