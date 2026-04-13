from unittest.mock import patch

from kctl_lib.ssh import SSHResult

from kctl_mm.commands.plugins import app


def test_plugins_list(runner, mock_context):
    mock_context.mm_exec.mmctl_json.return_value = [{"id": "com.example"}]
    result = runner.invoke(app, ["list"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.mm_exec.mmctl_json.assert_called_once_with(["plugin", "list"])


def test_plugins_install(runner, mock_context, tmp_path):
    tar = tmp_path / "myplugin.tar.gz"
    tar.write_bytes(b"fake")
    mock_context.mm_exec.mmctl.return_value = SSHResult(returncode=0, stdout="installed", stderr="")
    with patch("kctl_mm.commands.plugins.scp_upload") as su:
        result = runner.invoke(app, ["install", str(tar)], obj=mock_context)
        assert result.exit_code == 0
        su.assert_called_once()
        assert su.call_args[0][2] == "/tmp/myplugin.tar.gz"
    mock_context.mm_exec.mmctl.assert_called_once_with(["plugin", "install", "/tmp/myplugin.tar.gz"])


def test_plugins_enable(runner, mock_context):
    mock_context.mm_exec.mmctl.return_value = SSHResult(returncode=0, stdout="ok", stderr="")
    result = runner.invoke(app, ["enable", "com.example"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.mm_exec.mmctl.assert_called_once_with(["plugin", "enable", "com.example"])
