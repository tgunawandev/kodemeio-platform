from kctl_mm.commands.jobs import app


def test_jobs_list(runner, mock_context):
    mock_context.client.list_jobs.return_value = [{"id": "j1"}]
    result = runner.invoke(app, ["list"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.client.list_jobs.assert_called_once_with(job_type=None)


def test_jobs_status(runner, mock_context):
    mock_context.client.get_job.return_value = {"id": "j1", "status": "success"}
    result = runner.invoke(app, ["status", "j1"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.client.get_job.assert_called_once_with("j1")
