"""Tests for the storage command group."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from kctl_dbgate.cli import app

BASE = "https://dbgate.example.com"


def _mock_login(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="POST", url=f"{BASE}/auth/login", json={"accessToken": "tok"})


def _body(req: Any) -> dict[str, Any]:
    return json.loads(req.content)  # type: ignore[no-any-return]


def test_set_admin_password_requires_confirm(httpx_mock: HTTPXMock) -> None:
    runner = CliRunner()
    # Decline confirmation
    result = runner.invoke(
        app,
        ["storage", "set-admin-password", "--password", "newpw"],
        input="n\n",
    )
    assert result.exit_code == 0
    # No HTTP traffic
    reqs = [r for r in httpx_mock.get_requests() if r.url.path == "/storage/set-admin-password"]
    assert len(reqs) == 0


def test_set_admin_password_yes_sends_payload(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(method="POST", url=f"{BASE}/storage/set-admin-password", json={"ok": True})
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["storage", "set-admin-password", "--password", "newpw", "--yes"],
    )
    assert result.exit_code == 0, result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/storage/set-admin-password")
    body = _body(req)
    assert body["password"] == "newpw"
