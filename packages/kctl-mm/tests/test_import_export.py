from unittest.mock import patch

from kctl_lib.ssh import SSHResult

from kctl_mm.commands.import_export import app


def test_import_export_jobs(runner, mock_context):
    mock_context.mm_exec.mmctl_json.side_effect = [
        [{"id": "e1"}],
        [{"id": "i1"}],
    ]
    result = runner.invoke(app, ["jobs"], obj=mock_context)
    assert result.exit_code == 0
    calls = [c.args[0] for c in mock_context.mm_exec.mmctl_json.call_args_list]
    assert ["export", "job", "list"] in calls
    assert ["import", "job", "list"] in calls


def test_import_export_export(runner, mock_context):
    # stdout contains a 26-char job id
    job_id = "abcdefghijklmnopqrstuvwxyz"
    mock_context.mm_exec.mmctl.return_value = SSHResult(returncode=0, stdout=f"Export job created: {job_id}", stderr="")
    # Poll returns terminal status immediately
    mock_context.mm_exec.mmctl_json.return_value = {"id": job_id, "status": "success"}
    result = runner.invoke(app, ["export", "tpp"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.mm_exec.mmctl.assert_called_once_with(["export", "create", "tpp"])
    mock_context.mm_exec.mmctl_json.assert_called_with(["export", "job", "show", job_id])


def test_import_export_import(runner, mock_context, tmp_path):
    archive = tmp_path / "mybundle.zip"
    archive.write_bytes(b"data")
    job_id = "abcdefghijklmnopqrstuvwxyz"
    mock_context.mm_exec.mmctl.return_value = SSHResult(returncode=0, stdout=f"Import job: {job_id}", stderr="")
    mock_context.mm_exec.mmctl_json.return_value = {"id": job_id, "status": "success"}
    with patch("kctl_mm.commands.import_export.scp_upload") as su:
        result = runner.invoke(app, ["import", str(archive)], obj=mock_context)
        assert result.exit_code == 0
        su.assert_called_once()
        assert su.call_args[0][2] == "/mattermost/import/mybundle.zip"
    mock_context.mm_exec.mmctl.assert_called_once_with(["import", "process", "/mattermost/import/mybundle.zip"])
