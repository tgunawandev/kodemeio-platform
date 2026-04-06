"""Test config commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_config_show_json(runner: CliRunner, mock_client: MagicMock, mock_config: Path):
    p1, p2 = _patch_client(mock_client)
    # Also need to patch config imports in config_cmd module
    with (
        p1,
        p2,
        patch("kctl_zulip.commands.config_cmd.CONFIG_FILE", mock_config),
        patch(
            "kctl_zulip.commands.config_cmd.load_raw_config",
            return_value={
                "default_profile": "default",
                "profiles": {
                    "default": {
                        "zulip": {
                            "url": "https://zulip.test.io",
                            "email": "bot@test.io",
                            "api_key": "test-key-1234",
                        }
                    }
                },
            },
        ),
    ):
        result = runner.invoke(app, ["--json", "config", "show"])
    assert result.exit_code == 0


def test_config_profiles(runner: CliRunner, mock_client: MagicMock, mock_config: Path):
    p1, p2 = _patch_client(mock_client)
    with (
        p1,
        p2,
        patch("kctl_zulip.commands.config_cmd.get_profile_names", return_value=["default"]),
        patch("kctl_zulip.commands.config_cmd.resolve_active_profile_name", return_value="default"),
        patch("kctl_zulip.commands.config_cmd.get_default_profile", return_value="default"),
        patch("kctl_zulip.commands.config_cmd.get_service_config") as mock_svc,
        patch(
            "kctl_zulip.commands.config_cmd.get_all_services_in_profile",
            return_value={"zulip": {"url": "https://zulip.test.io"}},
        ),
        patch("kctl_zulip.commands.config_cmd._test_connection", return_value=(True, "9.0")),
    ):
        from kctl_zulip.core.config import ServiceConfig

        mock_svc.return_value = ServiceConfig(url="https://zulip.test.io", email="bot@test.io", api_key="key123")
        result = runner.invoke(app, ["config", "profiles"])
    assert result.exit_code == 0
