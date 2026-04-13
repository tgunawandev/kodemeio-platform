from __future__ import annotations

from typer.testing import CliRunner

from kctl_lib.ssh import SSHResult
from kctl_mm.commands.doctor import app


def test_doctor_all_ok(runner: CliRunner, mock_context) -> None:
    mock_context.client.ping.return_value = {"status": "OK"}
    mock_context.client.get_me.return_value = {"id": "u1", "username": "admin"}
    mock_context.mm_exec.mmctl.return_value = SSHResult(returncode=0, stdout="mmctl v10.5.0", stderr="")
    result = runner.invoke(app, [], obj=mock_context)
    assert result.exit_code == 0


def test_doctor_fails_on_ping_error(runner: CliRunner, mock_context) -> None:
    mock_context.client.ping.side_effect = Exception("network down")
    mock_context.client.get_me.return_value = {"id": "u1", "username": "admin"}
    mock_context.mm_exec.mmctl.return_value = SSHResult(returncode=0, stdout="v", stderr="")
    result = runner.invoke(app, [], obj=mock_context)
    assert result.exit_code == 1
