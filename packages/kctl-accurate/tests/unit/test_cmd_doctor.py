"""Tests for `kctl-accurate doctor`."""

from __future__ import annotations

from pathlib import Path

from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from kctl_accurate.cli import app


def test_doctor_fails_when_no_config(runner: CliRunner, fake_config_home: Path) -> None:
    """Empty config → all checks fail."""
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code != 0


def test_doctor_passes_with_valid_creds(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    write_profile(
        "tpp",
        {
            "api_token": "aut.token",
            "signature_secret": "secret-secret",
            "db_id": 12345,
            "host": "https://public.accurate.id",
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
        is_reusable=True,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://account.accurate.id/api/db-list.do",
        json={"s": True, "d": [{"id": 12345, "alias": "TPP", "host": "https://public.accurate.id"}]},
        is_reusable=True,
    )
    result = runner.invoke(app, ["-p", "tpp", "doctor"])
    assert result.exit_code == 0, result.output


def test_doctor_warns_on_unknown_db_id(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    write_profile(
        "tpp",
        {
            "api_token": "aut.token",
            "signature_secret": "secret-secret",
            "db_id": 99999,
            "host": "https://public.accurate.id",
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
        is_reusable=True,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://account.accurate.id/api/db-list.do",
        json={"s": True, "d": [{"id": 12345, "alias": "TPP", "host": "https://public.accurate.id"}]},
        is_reusable=True,
    )
    result = runner.invoke(app, ["-p", "tpp", "doctor"])
    # Warn-level → non-zero per kctl-* convention
    assert result.exit_code != 0
    combined = (result.stdout or "") + (result.stderr or "")
    assert "99999" in combined
