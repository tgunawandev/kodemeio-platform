"""Test doctor command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app
from kctl_zulip.core.config import ServiceConfig


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_doctor_all_pass(runner: CliRunner, mock_client: MagicMock):
    """Test doctor when all checks pass."""
    svc_config = ServiceConfig(url="https://zulip.test.io", email="bot@test.io", api_key="key123")

    mock_httpx_resp = MagicMock()
    mock_httpx_resp.status_code = 200
    mock_httpx_resp.json.return_value = {"zulip_version": "9.0", "zulip_feature_level": 300}

    mock_zulip_client = MagicMock()
    mock_zulip_client.get.return_value = {"email": "bot@test.io", "role": 200}
    mock_zulip_client.close.return_value = None

    p1, p2 = _patch_client(mock_client)
    with (
        p1,
        p2,
        patch("kctl_zulip.core.config.resolve_active_profile_name", return_value="default"),
        patch("kctl_zulip.core.config.get_service_config", return_value=svc_config),
        patch(
            "kctl_zulip.core.config.resolve_connection", return_value=("https://zulip.test.io", "bot@test.io", "key123")
        ),
        patch("httpx.get", return_value=mock_httpx_resp),
        patch("kctl_zulip.core.client.ZulipClient.__init__", return_value=None),
        patch("kctl_zulip.core.client.ZulipClient.get", return_value={"email": "bot@test.io", "role": 200}),
        patch("kctl_zulip.core.client.ZulipClient.close", return_value=None),
    ):
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0


def test_doctor_no_config(runner: CliRunner, mock_client: MagicMock):
    """Test doctor when no config is set."""
    empty_config = ServiceConfig(url="", email="", api_key="")

    p1, p2 = _patch_client(mock_client)
    with (
        p1,
        p2,
        patch("kctl_zulip.core.config.resolve_active_profile_name", return_value="default"),
        patch("kctl_zulip.core.config.get_service_config", return_value=empty_config),
        patch("kctl_zulip.core.config.resolve_connection", return_value=("", "", "")),
    ):
        result = runner.invoke(app, ["doctor"])
    # Should fail because config check fails
    assert result.exit_code == 1
