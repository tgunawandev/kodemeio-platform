from unittest.mock import patch

from kctl_lib.ssh import SSHResult

from kctl_mm.commands.mm_config import app


def test_mm_config_show(runner, mock_context):
    mock_context.client.get_config.return_value = {"ServiceSettings": {"SiteURL": "https://mm.idtpp.com"}}
    result = runner.invoke(app, ["show"], obj=mock_context)
    assert result.exit_code == 0


def test_mm_config_set(runner, mock_context):
    mock_context.mm_exec.mmctl.return_value = SSHResult(returncode=0, stdout="ok", stderr="")
    result = runner.invoke(app, ["set", "ServiceSettings.SiteURL", "https://new"], obj=mock_context)
    assert result.exit_code == 0
    mock_context.mm_exec.mmctl.assert_called_once_with(["config", "set", "ServiceSettings.SiteURL", "https://new"])


def test_mm_config_export(runner, mock_context, tmp_path):
    mock_context.mm_exec.mmctl.return_value = SSHResult(returncode=0, stdout="exported", stderr="")
    with patch("kctl_mm.commands.mm_config.scp_download") as sd:
        result = runner.invoke(app, ["export", str(tmp_path / "cfg.json")], obj=mock_context)
        assert result.exit_code == 0
        sd.assert_called_once()
