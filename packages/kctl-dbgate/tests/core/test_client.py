"""Tests for DBGateClient - correct DBGate auth flow."""

from __future__ import annotations

import json

import pytest
from kctl_lib.exceptions import APIError
from pytest_httpx import HTTPXMock

from kctl_dbgate.core.client import DBGateClient

BASE = "https://dbgate.example.com"


def _new_client() -> DBGateClient:
    return DBGateClient(base_url=BASE, login="admin", password="hunter2")


def test_login_calls_correct_path_and_body(httpx_mock: HTTPXMock) -> None:
    """POST /auth/login (no /api prefix), body has amoid=logins."""
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/auth/login",
        json={"accessToken": "tok"},
    )
    client = _new_client()
    token = client.login()
    assert token == "tok"

    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    req = requests[0]
    assert req.url.path == "/auth/login"
    assert req.url.path != "/api/auth/login"
    body = json.loads(req.content)
    assert body == {"amoid": "logins", "login": "admin", "password": "hunter2"}


def test_call_auto_logins_when_token_missing(httpx_mock: HTTPXMock) -> None:
    """First call() with no cached token auto-logins."""
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/auth/login",
        json={"accessToken": "tok"},
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/list",
        json=[],
    )
    client = _new_client()
    result = client.call("/connections/list")
    assert result == []

    requests = httpx_mock.get_requests()
    # Exactly one login + one connections/list
    login_reqs = [r for r in requests if r.url.path == "/auth/login"]
    assert len(login_reqs) == 1


def test_call_uses_bearer_token_header(httpx_mock: HTTPXMock) -> None:
    """After login, subsequent requests carry Authorization: Bearer <tok>."""
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/auth/login",
        json={"accessToken": "tok"},
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/list",
        json=[],
    )
    client = _new_client()
    client.call("/connections/list")

    conn_req = next(r for r in httpx_mock.get_requests() if r.url.path == "/connections/list")
    assert conn_req.headers.get("authorization") == "Bearer tok"
    # Ensure we don't send x-access-token
    assert conn_req.headers.get("x-access-token") is None


def test_call_retries_once_on_401(httpx_mock: HTTPXMock) -> None:
    """On 401 from an expired token, re-login once then retry succeeds."""
    # First login
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/auth/login",
        json={"accessToken": "tok1"},
    )
    # First connections/list call: 401
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/list",
        status_code=401,
        text="token expired",
    )
    # Re-login
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/auth/login",
        json={"accessToken": "tok2"},
    )
    # Retry: 200
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/list",
        json=[{"_id": "a"}],
    )

    client = _new_client()
    result = client.call("/connections/list")
    assert result == [{"_id": "a"}]

    login_reqs = [r for r in httpx_mock.get_requests() if r.url.path == "/auth/login"]
    assert len(login_reqs) == 2


def test_api_error_message_surfaces(httpx_mock: HTTPXMock) -> None:
    """5xx with apiErrorMessage payload raises APIError with that message."""
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/auth/login",
        json={"accessToken": "tok"},
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/list",
        status_code=500,
        json={"apiErrorMessage": "boom"},
    )
    client = _new_client()
    with pytest.raises(APIError) as excinfo:
        client.call("/connections/list")
    assert "boom" in str(excinfo.value)
