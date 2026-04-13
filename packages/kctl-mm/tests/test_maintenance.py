from kctl_lib.ssh import SSHResult

from kctl_mm.commands.maintenance import app


def test_maintenance_cleanup(runner, mock_context):
    mock_context.mm_exec.mmctl.return_value = SSHResult(returncode=0, stdout="done", stderr="")
    result = runner.invoke(app, ["cleanup"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.mm_exec.mmctl.assert_called_once_with(["maintenance", "cleanup"])


def test_maintenance_vacuum(runner, mock_context):
    mock_context.mm_exec.docker_compose.return_value = SSHResult(returncode=0, stdout="VACUUM", stderr="")
    result = runner.invoke(app, ["vacuum"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.mm_exec.docker_compose.assert_called_once()
    args = mock_context.mm_exec.docker_compose.call_args[0][0]
    assert "VACUUM ANALYZE;" in args
    assert "mm-postgres" in args
