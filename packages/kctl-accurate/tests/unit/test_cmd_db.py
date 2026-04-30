"""Tests for `kctl-accurate db` commands."""

from __future__ import annotations

import json

from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from kctl_accurate.cli import app

_HOST = "https://public.accurate.id"

_DB_LIST_RESPONSE = {
    "s": True,
    "d": [
        {"id": 101, "alias": "PT Alpha", "host": "https://alpha.accurate.id"},
        {"id": 202, "alias": "PT Beta", "host": "https://beta.accurate.id"},
        {"id": 303, "alias": "PT Gamma", "host": "https://gamma.accurate.id"},
    ],
}

_OPEN_DB_RESPONSE = {
    "s": True,
    "d": {
        "session": "sess-abc123",
        "db_id": 101,
        "alias": "PT Alpha",
        "host": "https://alpha.accurate.id",
    },
}

_TOKEN_INFO_RESPONSE = {
    "s": True,
    "d": {
        "user": {"name": "Tri Gunawan", "email": "tri@idtpp.com"},
        "database": {"id": 12345, "alias": "PT TPP Indonesia", "host": "https://public.accurate.id"},
    },
}


def _setup_profile(write_profile) -> None:
    write_profile(
        "tpp",
        {
            "api_token": "aut.fake-token",
            "signature_secret": "secretsecret",
            "db_id": 12345,
            "host": _HOST,
        },
    )


# ── db list-companies ──────────────────────────────────────────────────────────


def test_db_list_companies_renders_table(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    """``db list-companies`` calls db-list.do and renders a Rich table with 3 rows."""
    _setup_profile(write_profile)
    httpx_mock.add_response(
        method="GET",
        url="https://account.accurate.id/api/db-list.do",
        json=_DB_LIST_RESPONSE,
    )
    result = runner.invoke(app, ["-p", "tpp", "db", "list-companies"])
    assert result.exit_code == 0, result.output + (result.stderr or "")
    # All three companies should appear in the output
    assert "PT Alpha" in result.output
    assert "PT Beta" in result.output
    assert "PT Gamma" in result.output
    assert "101" in result.output


def test_db_list_companies_json(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    """``db list-companies --json`` returns a JSON array of companies."""
    _setup_profile(write_profile)
    httpx_mock.add_response(
        method="GET",
        url="https://account.accurate.id/api/db-list.do",
        json=_DB_LIST_RESPONSE,
    )
    result = runner.invoke(app, ["-p", "tpp", "--json", "db", "list-companies"])
    assert result.exit_code == 0, result.output + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert len(payload) == 3
    assert payload[0]["id"] == 101
    assert payload[0]["alias"] == "PT Alpha"


def test_db_info_renders_user_and_db(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    """``db info`` calls api-token.do and renders user + database info."""
    _setup_profile(write_profile)
    httpx_mock.add_response(
        method="POST",
        url="https://account.accurate.id/api/api-token.do",
        json=_TOKEN_INFO_RESPONSE,
    )
    result = runner.invoke(app, ["-p", "tpp", "db", "info"])
    assert result.exit_code == 0, result.output + (result.stderr or "")
    assert "Tri Gunawan" in result.output
    assert "tri@idtpp.com" in result.output
    assert "12345" in result.output
    assert "PT TPP Indonesia" in result.output


def test_db_open_pretty(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    """``db open 101`` calls open-db.do and renders a panel."""
    _setup_profile(write_profile)
    httpx_mock.add_response(
        method="GET",
        url="https://account.accurate.id/api/open-db.do?id=101",
        json=_OPEN_DB_RESPONSE,
    )
    result = runner.invoke(app, ["-p", "tpp", "db", "open", "101"])
    assert result.exit_code == 0, result.output + (result.stderr or "")
    assert "sess-abc123" in result.output or "PT Alpha" in result.output


def test_db_open_json(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    """``db open --json 101`` returns the raw session dict as JSON."""
    _setup_profile(write_profile)
    httpx_mock.add_response(
        method="GET",
        url="https://account.accurate.id/api/open-db.do?id=101",
        json=_OPEN_DB_RESPONSE,
    )
    result = runner.invoke(app, ["-p", "tpp", "--json", "db", "open", "101"])
    assert result.exit_code == 0, result.output + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert payload["session"] == "sess-abc123"
    assert payload["alias"] == "PT Alpha"
