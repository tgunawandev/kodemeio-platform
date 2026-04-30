"""Tests for `kctl-accurate dashboard` command."""

from __future__ import annotations

import json
import re

from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from kctl_accurate.cli import app

_HOST = "https://public.accurate.id"

_TOKEN_INFO_RESPONSE = {
    "s": True,
    "d": {
        "user": {"name": "Tri Gunawan", "email": "tri@idtpp.com"},
        "database": {"id": 12345, "alias": "PT TPP Indonesia", "host": "https://public.accurate.id"},
    },
}


# A minimal sp block used for each count response (pageSize=1).
def _count_response(count: int) -> dict:
    return {
        "s": True,
        "d": [],
        "sp": {"page": 1, "pageSize": 1, "pageCount": count, "rowCount": count, "start": 0, "limit": None},
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


def _mock_all_endpoints(httpx_mock: HTTPXMock) -> None:
    """Register mocks for token-info + all 5 module count endpoints."""
    httpx_mock.add_response(
        method="POST",
        url="https://account.accurate.id/api/api-token.do",
        json=_TOKEN_INFO_RESPONSE,
    )
    for path, count in [
        (r"/accurate/api/customer/list\.do", 1500),
        (r"/accurate/api/vendor/list\.do", 320),
        (r"/accurate/api/item/list\.do", 850),
        (r"/accurate/api/sales-invoice/list\.do", 4200),
        (r"/accurate/api/purchase-invoice/list\.do", 990),
    ]:
        httpx_mock.add_response(
            method="GET",
            url=re.compile(rf"{re.escape(_HOST)}{path}"),
            json=_count_response(count),
        )


def test_dashboard_renders(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    """``dashboard`` renders user info, DB info, and module counts."""
    _setup_profile(write_profile)
    _mock_all_endpoints(httpx_mock)

    result = runner.invoke(app, ["-p", "tpp", "dashboard"])
    assert result.exit_code == 0, result.output + (result.stderr or "")

    # User info
    assert "Tri Gunawan" in result.output
    assert "tri@idtpp.com" in result.output

    # DB info
    assert "12345" in result.output
    assert "PT TPP Indonesia" in result.output

    # Module names must appear
    assert "customers" in result.output
    assert "vendors" in result.output
    assert "sales-invoices" in result.output


def test_dashboard_json(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    """``dashboard --json`` returns structured JSON with user, database, and counts."""
    _setup_profile(write_profile)
    _mock_all_endpoints(httpx_mock)

    result = runner.invoke(app, ["-p", "tpp", "--json", "dashboard"])
    assert result.exit_code == 0, result.output + (result.stderr or "")

    payload = json.loads(result.stdout)

    # Top-level keys
    assert "user" in payload
    assert "database" in payload
    assert "counts" in payload

    # User fields
    assert payload["user"]["name"] == "Tri Gunawan"
    assert payload["user"]["email"] == "tri@idtpp.com"

    # Database fields
    assert payload["database"]["id"] == 12345
    assert payload["database"]["alias"] == "PT TPP Indonesia"

    # All 5 modules present with correct counts
    counts = payload["counts"]
    assert counts["customers"] == 1500
    assert counts["vendors"] == 320
    assert counts["items"] == 850
    assert counts["sales-invoices"] == 4200
    assert counts["purchase-invoices"] == 990
