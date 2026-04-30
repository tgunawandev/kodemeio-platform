"""Tests for `kctl-accurate auth` commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from kctl_accurate.cli import app


def _setup_profile(write_profile, host: str = "https://public.accurate.id") -> None:
    write_profile(
        "tpp",
        {
            "api_token": "aut.fake-token",
            "signature_secret": "secretsecret",
            "db_id": 12345,
            "host": host,
        },
    )


def test_auth_token_info_pretty(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    _setup_profile(write_profile)
    httpx_mock.add_response(
        method="POST",
        url="https://account.accurate.id/api/api-token.do",
        json={
            "s": True,
            "d": {
                "user": {"name": "Tri Gunawan", "email": "tri@idtpp.com"},
                "database": {"id": 12345, "alias": "PT TPP Indonesia", "host": "https://public.accurate.id"},
            },
        },
    )
    result = runner.invoke(app, ["-p", "tpp", "auth", "token-info"])
    assert result.exit_code == 0, result.output + (result.stderr or "")
    assert "Tri Gunawan" in result.stdout
    assert "12345" in result.stdout


def test_auth_token_info_json(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    _setup_profile(write_profile)
    httpx_mock.add_response(
        method="POST",
        url="https://account.accurate.id/api/api-token.do",
        json={"s": True, "d": {"user": {"name": "tri"}, "database": {"id": 1, "alias": "x", "host": "h"}}},
    )
    result = runner.invoke(app, ["-p", "tpp", "--json", "auth", "token-info"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["d"]["user"]["name"] == "tri"


def test_auth_token_info_401_exits_nonzero(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    _setup_profile(write_profile)
    httpx_mock.add_response(
        method="POST",
        url="https://account.accurate.id/api/api-token.do",
        status_code=401,
        text="invalid signature",
        is_reusable=True,
    )
    result = runner.invoke(app, ["-p", "tpp", "auth", "token-info"])
    assert result.exit_code != 0
    # The error message should mention auth or 401 — the exact exit code
    # depends on whether kctl_lib has been upgraded to route by subclass.
    # For now, any non-zero code is acceptable since handle_cli_error
    # currently exits 1 for all KctlError subclasses.


def test_auth_logout_calls_logout(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    _setup_profile(write_profile)
    httpx_mock.add_response(
        method="POST",
        url="https://account.accurate.id/api/logout.do",
        json={"s": True, "d": {"loggedOut": True}},
    )
    result = runner.invoke(app, ["-p", "tpp", "auth", "logout"])
    assert result.exit_code == 0


def test_auth_missing_creds_exits_nonzero(runner: CliRunner, fake_config_home: Path) -> None:
    """No profile present → ConfigError → non-zero exit."""
    result = runner.invoke(app, ["auth", "token-info"])
    assert result.exit_code != 0
