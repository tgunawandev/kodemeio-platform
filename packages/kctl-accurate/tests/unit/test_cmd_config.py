"""Tests for `kctl-accurate config` commands."""

from __future__ import annotations

from pathlib import Path

import yaml
from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from kctl_accurate.cli import app


def test_config_show_masks_secrets(runner: CliRunner, write_profile) -> None:
    write_profile(
        "tpp",
        {
            "api_token": "aut.abcdefghijklmnop",
            "signature_secret": "this-is-secret-1234",
            "db_id": 12345,
        },
    )
    result = runner.invoke(app, ["config", "show", "tpp"])
    assert result.exit_code == 0, result.output
    assert "this-is-secret-1234" not in result.stdout
    assert "aut." in result.stdout
    assert "mnop" in result.stdout


def test_config_list_shows_profiles(runner: CliRunner, write_profile) -> None:
    write_profile("tpp", {"api_token": "t", "signature_secret": "s", "db_id": 1})
    result = runner.invoke(app, ["config", "list"])
    assert result.exit_code == 0
    assert "tpp" in result.stdout


def test_config_use_changes_default(runner: CliRunner, fake_config_home: Path) -> None:
    (fake_config_home / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "default_profile": "tpp",
                "profiles": {
                    "tpp": {"accurate": {"api_token": "t", "signature_secret": "s", "db_id": 1}},
                    "abc": {"accurate": {"api_token": "t", "signature_secret": "s", "db_id": 2}},
                },
            }
        )
    )
    result = runner.invoke(app, ["config", "use", "abc"])
    assert result.exit_code == 0
    saved = yaml.safe_load((fake_config_home / "config.yaml").read_text())
    assert saved["default_profile"] == "abc"


def test_config_add_creates_profile(runner: CliRunner, fake_config_home: Path) -> None:
    result = runner.invoke(
        app,
        [
            "config",
            "add",
            "newprof",
            "--api-token",
            "aut.token",
            "--signature-secret",
            "secret123secret",
            "--db-id",
            "99",
        ],
    )
    assert result.exit_code == 0, result.output
    saved = yaml.safe_load((fake_config_home / "config.yaml").read_text())
    assert saved["profiles"]["newprof"]["accurate"]["db_id"] == 99


def test_config_remove_drops_profile(runner: CliRunner, write_profile, fake_config_home: Path) -> None:
    write_profile("tpp", {"api_token": "t", "signature_secret": "s", "db_id": 1})
    result = runner.invoke(app, ["config", "remove", "tpp"])
    assert result.exit_code == 0
    saved = yaml.safe_load((fake_config_home / "config.yaml").read_text())
    assert "tpp" not in saved.get("profiles", {})


def test_config_set_patches_field(runner: CliRunner, write_profile, fake_config_home: Path) -> None:
    write_profile("tpp", {"api_token": "t", "signature_secret": "s", "db_id": 1})
    result = runner.invoke(app, ["config", "set", "db_id", "777", "-p", "tpp"])
    assert result.exit_code == 0
    saved = yaml.safe_load((fake_config_home / "config.yaml").read_text())
    assert saved["profiles"]["tpp"]["accurate"]["db_id"] == 777


def test_config_test_succeeds_on_valid_creds(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    write_profile(
        "tpp",
        {
            "api_token": "aut.token",
            "signature_secret": "secret123secret",
            "db_id": 12345,
        },
    )
    httpx_mock.add_response(
        method="POST",
        url="https://account.accurate.id/api/api-token.do",
        json={
            "s": True,
            "d": {
                "user": {"name": "tri"},
                "database": {"id": 12345, "alias": "TPP", "host": "https://public.accurate.id"},
            },
        },
    )
    result = runner.invoke(app, ["config", "test", "tpp"])
    assert result.exit_code == 0, result.output


def test_config_test_fails_on_401(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    write_profile(
        "tpp",
        {
            "api_token": "aut.bad",
            "signature_secret": "wrong-secret",
            "db_id": 1,
        },
    )
    httpx_mock.add_response(
        method="POST",
        url="https://account.accurate.id/api/api-token.do",
        status_code=401,
        text="invalid signature",
        is_reusable=True,
    )
    result = runner.invoke(app, ["config", "test", "tpp"])
    assert result.exit_code != 0
