"""Tests for kctl-redis config commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_redis.cli import app
from kctl_redis.core.callbacks import AppContext
from kctl_redis.core.config import ServiceConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ctx(json_mode: bool = False) -> AppContext:
    """AppContext without a real client (config commands don't need one)."""
    return AppContext(quiet=True, json_mode=json_mode)


def invoke(runner: CliRunner, app_ctx: AppContext, args: list[str]) -> object:
    return runner.invoke(app, args, obj=app_ctx, catch_exceptions=False)


SAMPLE_SVC = ServiceConfig(
    host="10.0.0.5",
    port=6379,
    username="default",
    password="secretpassword",
    db=0,
    ssh_host="49.13.14.79",
    ssh_port=22,
    ssh_user="root",
    ssh_key="~/.ssh/id_ed25519",
)


# ---------------------------------------------------------------------------
# config add
# ---------------------------------------------------------------------------


class TestConfigAdd:
    def test_add_profile(self, runner: CliRunner, mock_config: Path) -> None:
        result = runner.invoke(
            app,
            [
                "config",
                "add",
                "myprofile",
                "--host",
                "10.0.0.5",
                "--password",
                "s3cr3t",
                "--ssh-host",
                "jump.example.com",
            ],
            obj=make_ctx(),
            catch_exceptions=False,
        )
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_add_profile_with_all_options(self, runner: CliRunner, mock_config: Path) -> None:
        result = runner.invoke(
            app,
            [
                "config",
                "add",
                "full-profile",
                "--host",
                "10.0.0.10",
                "--port",
                "6380",
                "--username",
                "redisuser",
                "--password",
                "p@ssw0rd",
                "--db",
                "2",
                "--ssh-host",
                "bastion.example.com",
                "--ssh-port",
                "2222",
                "--ssh-user",
                "deploy",
                "--ssh-key",
                "~/.ssh/deploy_key",
            ],
            obj=make_ctx(),
            catch_exceptions=False,
        )
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_add_profile_saves_to_config(self, runner: CliRunner, mock_config: Path) -> None:
        runner.invoke(
            app,
            ["config", "add", "saved-profile", "--host", "10.1.2.3", "--ssh-host", "jump.io"],
            obj=make_ctx(),
        )
        # Config file should now exist
        assert mock_config.exists() or any(mock_config.parent.iterdir())


# ---------------------------------------------------------------------------
# config use
# ---------------------------------------------------------------------------


class TestConfigUse:
    def test_use_existing_profile(self, runner: CliRunner, mock_config: Path) -> None:
        # First add a profile, then switch to it
        runner.invoke(
            app,
            ["config", "add", "prod", "--host", "10.0.0.1", "--ssh-host", "jump.example.com"],
            obj=make_ctx(),
        )
        result = runner.invoke(app, ["config", "use", "prod"], obj=make_ctx(), catch_exceptions=False)
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_use_nonexistent_profile_exits_1(self, runner: CliRunner, mock_config: Path) -> None:
        result = runner.invoke(app, ["config", "use", "nonexistent"], obj=make_ctx())
        assert result.exit_code == 1  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# config profiles
# ---------------------------------------------------------------------------


class TestConfigProfiles:
    def test_profiles_empty(self, runner: CliRunner, mock_config: Path) -> None:
        result = runner.invoke(app, ["config", "profiles"], obj=make_ctx(), catch_exceptions=False)
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_profiles_lists_added_profiles(self, runner: CliRunner, mock_config: Path) -> None:
        runner.invoke(
            app,
            ["config", "add", "alpha", "--host", "10.0.0.1", "--ssh-host", "jump.example.com"],
            obj=make_ctx(),
        )
        runner.invoke(
            app,
            ["config", "add", "beta", "--host", "10.0.0.2", "--ssh-host", "jump.example.com"],
            obj=make_ctx(),
        )
        result = runner.invoke(app, ["config", "profiles"], obj=make_ctx(), catch_exceptions=False)
        assert result.exit_code == 0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# config show
# ---------------------------------------------------------------------------


class TestConfigShow:
    def test_show_masks_password(self, runner: CliRunner, mock_config: Path) -> None:
        runner.invoke(
            app,
            [
                "config",
                "add",
                "show-test",
                "--host",
                "10.0.0.5",
                "--password",
                "supersecret1234",
                "--ssh-host",
                "jump.example.com",
            ],
            obj=make_ctx(),
        )
        runner.invoke(app, ["config", "use", "show-test"], obj=make_ctx())
        result = runner.invoke(app, ["config", "show"], obj=make_ctx(), catch_exceptions=False)
        assert result.exit_code == 0  # type: ignore[attr-defined]
        # Password must not appear in plain text
        assert "supersecret1234" not in (result.output or "")  # type: ignore[attr-defined]

    def test_show_no_profile_configured_exits_1(self, runner: CliRunner, mock_config: Path) -> None:
        result = runner.invoke(app, ["config", "show"], obj=make_ctx())
        assert result.exit_code == 1  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# config current
# ---------------------------------------------------------------------------


class TestConfigCurrent:
    def test_current_no_profile_exits_1(self, runner: CliRunner, mock_config: Path) -> None:
        result = runner.invoke(app, ["config", "current"], obj=make_ctx())
        assert result.exit_code == 1  # type: ignore[attr-defined]

    def test_current_shows_active_profile(self, runner: CliRunner, mock_config: Path) -> None:
        runner.invoke(
            app,
            ["config", "add", "active", "--host", "10.0.0.1", "--ssh-host", "jump.example.com"],
            obj=make_ctx(),
        )
        runner.invoke(app, ["config", "use", "active"], obj=make_ctx())
        result = runner.invoke(app, ["config", "current"], obj=make_ctx(), catch_exceptions=False)
        assert result.exit_code == 0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# config remove
# ---------------------------------------------------------------------------


class TestConfigRemove:
    def test_remove_with_force(self, runner: CliRunner, mock_config: Path) -> None:
        runner.invoke(
            app,
            ["config", "add", "to-remove", "--host", "10.0.0.1", "--ssh-host", "jump.example.com"],
            obj=make_ctx(),
        )
        result = runner.invoke(
            app, ["config", "remove", "to-remove", "--force"], obj=make_ctx(), catch_exceptions=False
        )
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_remove_confirms_without_force(self, runner: CliRunner, mock_config: Path) -> None:
        runner.invoke(
            app,
            ["config", "add", "confirm-remove", "--host", "10.0.0.1", "--ssh-host", "jump.example.com"],
            obj=make_ctx(),
        )
        result = runner.invoke(
            app, ["config", "remove", "confirm-remove"], obj=make_ctx(), input="y\n", catch_exceptions=False
        )
        assert result.exit_code == 0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# config set
# ---------------------------------------------------------------------------


class TestConfigSet:
    def test_set_valid_field(self, runner: CliRunner, mock_config: Path) -> None:
        runner.invoke(
            app,
            ["config", "add", "settest", "--host", "10.0.0.1", "--ssh-host", "jump.example.com"],
            obj=make_ctx(),
        )
        runner.invoke(app, ["config", "use", "settest"], obj=make_ctx())
        result = runner.invoke(app, ["config", "set", "host", "10.0.0.99"], obj=make_ctx(), catch_exceptions=False)
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_set_invalid_field_exits_1(self, runner: CliRunner, mock_config: Path) -> None:
        runner.invoke(
            app,
            ["config", "add", "setbad", "--host", "10.0.0.1", "--ssh-host", "jump.example.com"],
            obj=make_ctx(),
        )
        runner.invoke(app, ["config", "use", "setbad"], obj=make_ctx())
        result = runner.invoke(app, ["config", "set", "nonexistentfield", "value"], obj=make_ctx())
        assert result.exit_code == 1  # type: ignore[attr-defined]

    def test_set_integer_field(self, runner: CliRunner, mock_config: Path) -> None:
        runner.invoke(
            app,
            ["config", "add", "inttest", "--host", "10.0.0.1", "--ssh-host", "jump.example.com"],
            obj=make_ctx(),
        )
        runner.invoke(app, ["config", "use", "inttest"], obj=make_ctx())
        result = runner.invoke(app, ["config", "set", "port", "6380"], obj=make_ctx(), catch_exceptions=False)
        assert result.exit_code == 0  # type: ignore[attr-defined]

    def test_set_password_is_masked_in_output(self, runner: CliRunner, mock_config: Path) -> None:
        runner.invoke(
            app,
            ["config", "add", "masktest", "--host", "10.0.0.1", "--ssh-host", "jump.example.com"],
            obj=make_ctx(),
        )
        runner.invoke(app, ["config", "use", "masktest"], obj=make_ctx())
        result = runner.invoke(
            app, ["config", "set", "password", "mysecretpassword"], obj=make_ctx(), catch_exceptions=False
        )
        assert result.exit_code == 0  # type: ignore[attr-defined]
        assert "mysecretpassword" not in (result.output or "")  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# _mask helper (via config show)
# ---------------------------------------------------------------------------


class TestMaskHelper:
    """Test the password masking behavior indirectly via config show."""

    def test_short_password_fully_masked(self, runner: CliRunner, mock_config: Path) -> None:
        runner.invoke(
            app,
            ["config", "add", "shortpass", "--host", "10.0.0.1", "--password", "abc", "--ssh-host", "j.io"],
            obj=make_ctx(),
        )
        runner.invoke(app, ["config", "use", "shortpass"], obj=make_ctx())
        result = runner.invoke(app, ["config", "show"], obj=make_ctx(), catch_exceptions=False)
        assert result.exit_code == 0  # type: ignore[attr-defined]
        assert "abc" not in (result.output or "")  # type: ignore[attr-defined]

    def test_long_password_shows_partial(self, runner: CliRunner, mock_config: Path) -> None:
        password = "abcdefghijklmnop"  # 16 chars
        runner.invoke(
            app,
            [
                "config",
                "add",
                "longpass",
                "--host",
                "10.0.0.1",
                "--password",
                password,
                "--ssh-host",
                "j.io",
            ],
            obj=make_ctx(),
        )
        runner.invoke(app, ["config", "use", "longpass"], obj=make_ctx())
        result = runner.invoke(app, ["config", "show"], obj=make_ctx(), catch_exceptions=False)
        assert result.exit_code == 0  # type: ignore[attr-defined]
        # Full password must not appear
        assert password not in (result.output or "")  # type: ignore[attr-defined]
        # First 4 chars should appear
        assert "abcd" in (result.output or "")  # type: ignore[attr-defined]
