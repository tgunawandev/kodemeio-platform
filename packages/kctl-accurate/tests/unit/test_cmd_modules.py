"""Tests for the module command factory (build_module_app).

Uses pytest-httpx to intercept HTTP calls and typer.testing.CliRunner
to drive the CLI end-to-end without a real Accurate API.

Note on URL matching: pytest-httpx 0.36 matches URLs *including* query
params when a plain string URL is given.  We use ``re.compile`` so the
mock accepts any request whose URL starts with the given path regardless
of which query params the SDK appends (sp.page, sp.pageSize, filter.*).
"""

from __future__ import annotations

import json
import re

from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from kctl_accurate.cli import app

# Host used in all profiles — must match the httpx_mock URL base.
_HOST = "https://public.accurate.id"

# A minimal single-row customer payload that list.do returns.
_CUSTOMER_ROW = {
    "id": 1001,
    "name": "PT Maju Bersama",
    "customerNo": "C-001",
    "email": "info@majubersama.com",
    "mobilePhone": "08123456789",
    "npwpNo": "01.234.567.8-901.000",
    "suspended": False,
}

_LIST_RESPONSE = {
    "s": True,
    "d": [_CUSTOMER_ROW],
    "sp": {"page": 1, "pageSize": 100, "pageCount": 1, "rowCount": 1, "start": 0, "limit": None},
}

_DETAIL_RESPONSE = {
    "s": True,
    "d": _CUSTOMER_ROW,
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


# ── customers list ─────────────────────────────────────────────────────────────


def test_customers_list_renders_table(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    """``customers list`` fetches pages and renders a Rich table."""
    _setup_profile(write_profile)
    httpx_mock.add_response(
        method="GET",
        url=re.compile(rf"{re.escape(_HOST)}/accurate/api/customer/list\.do"),
        json=_LIST_RESPONSE,
    )
    result = runner.invoke(app, ["-p", "tpp", "customers", "list"])
    assert result.exit_code == 0, result.output + (result.stderr or "")
    # Row ID and name should appear somewhere in the output
    assert "1001" in result.output or "PT Maju Bersama" in result.output


def test_customers_list_since_adds_filter_params(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    """``customers list --since 2026-04-01`` injects the lastUpdated filter params."""
    _setup_profile(write_profile)
    httpx_mock.add_response(
        method="GET",
        url=re.compile(rf"{re.escape(_HOST)}/accurate/api/customer/list\.do"),
        json=_LIST_RESPONSE,
    )
    result = runner.invoke(app, ["-p", "tpp", "customers", "list", "--since", "2026-04-01"])
    assert result.exit_code == 0, result.output + (result.stderr or "")

    # Inspect the recorded request to confirm filter params were sent
    requests = httpx_mock.get_requests()
    assert requests, "No requests were recorded"
    req = requests[0]
    params = dict(req.url.params)
    assert params.get("filter.lastUpdated.op") == "GREATER_EQUAL"
    assert params.get("filter.lastUpdated.val[0]") == "01/04/2026"


def test_customers_list_json_mode(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    """``--json customers list`` returns a JSON array."""
    _setup_profile(write_profile)
    httpx_mock.add_response(
        method="GET",
        url=re.compile(rf"{re.escape(_HOST)}/accurate/api/customer/list\.do"),
        json=_LIST_RESPONSE,
    )
    result = runner.invoke(app, ["-p", "tpp", "--json", "customers", "list"])
    assert result.exit_code == 0, result.output + (result.stderr or "")
    payload = json.loads(result.output)
    assert isinstance(payload, list)
    assert payload[0]["id"] == 1001
    assert payload[0]["name"] == "PT Maju Bersama"


# ── customers get ──────────────────────────────────────────────────────────────


def test_customers_get_renders_detail(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    """``customers get 1001`` fetches detail.do and renders a panel."""
    _setup_profile(write_profile)
    httpx_mock.add_response(
        method="GET",
        url=re.compile(rf"{re.escape(_HOST)}/accurate/api/customer/detail\.do"),
        json=_DETAIL_RESPONSE,
    )
    result = runner.invoke(app, ["-p", "tpp", "customers", "get", "1001"])
    assert result.exit_code == 0, result.output + (result.stderr or "")
    # Should show the name or ID in the panel
    assert "PT Maju Bersama" in result.output or "1001" in result.output


# ── taxes count (different module — proves the factory is generic) ─────────────


def test_taxes_count_returns_row_count(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    """``taxes count`` hits list.do?sp.pageSize=1 and extracts sp.rowCount."""
    _setup_profile(write_profile)
    httpx_mock.add_response(
        method="GET",
        url=re.compile(rf"{re.escape(_HOST)}/accurate/api/tax/list\.do"),
        json={
            "s": True,
            "d": [],
            "sp": {"page": 1, "pageSize": 1, "pageCount": 7, "rowCount": 7, "start": 0, "limit": None},
        },
    )
    result = runner.invoke(app, ["-p", "tpp", "taxes", "count"])
    assert result.exit_code == 0, result.output + (result.stderr or "")
    assert "7" in result.output


# ── customers list --days (shorthand) ─────────────────────────────────────────


def test_customers_list_days_adds_filter_params(runner: CliRunner, write_profile, httpx_mock: HTTPXMock) -> None:
    """``customers list --days 7`` injects a lastUpdated filter for 7 days ago."""
    _setup_profile(write_profile)
    httpx_mock.add_response(
        method="GET",
        url=re.compile(rf"{re.escape(_HOST)}/accurate/api/customer/list\.do"),
        json=_LIST_RESPONSE,
    )
    result = runner.invoke(app, ["-p", "tpp", "customers", "list", "--days", "7"])
    assert result.exit_code == 0, result.output + (result.stderr or "")

    requests = httpx_mock.get_requests()
    assert requests
    params = dict(requests[0].url.params)
    assert params.get("filter.lastUpdated.op") == "GREATER_EQUAL"
    # We can't know the exact date but the format should be DD/MM/YYYY
    val = params.get("filter.lastUpdated.val[0]", "")
    assert len(val) == 10 and val[2] == "/" and val[5] == "/"
