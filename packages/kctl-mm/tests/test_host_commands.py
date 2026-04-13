from typer.testing import CliRunner

from kctl_mm.commands import deploy, logs, status
from kctl_lib.ssh import SSHResult


def test_status_runs_compose_ps(runner: CliRunner, mock_context) -> None:
    mock_context.mm_exec.docker_compose.return_value = SSHResult(returncode=0, stdout="ok", stderr="")
    result = runner.invoke(status.app, [], obj=mock_context)
    assert result.exit_code == 0
    mock_context.mm_exec.docker_compose.assert_called_once_with(["ps"])


def test_logs_calls_compose_logs(runner: CliRunner, mock_context) -> None:
    mock_context.mm_exec.docker_compose.return_value = SSHResult(returncode=0, stdout="ok", stderr="")
    result = runner.invoke(logs.app, ["--lines", "50", "mattermost"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.mm_exec.docker_compose.assert_called_once_with(["logs", "--tail", "50", "mattermost"])


def test_deploy_restart(runner: CliRunner, mock_context) -> None:
    mock_context.mm_exec.docker_compose.return_value = SSHResult(returncode=0, stdout="", stderr="")
    result = runner.invoke(deploy.app, ["restart"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.mm_exec.docker_compose.assert_called_once_with(["restart"])


def test_deploy_rebuild(runner, mock_context):
    mock_context.mm_exec.docker_compose.return_value = SSHResult(returncode=0, stdout="", stderr="")
    result = runner.invoke(deploy.app, ["rebuild"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.mm_exec.docker_compose.assert_called_once_with(["up", "-d", "--build"])
