"""Tests for the sessions command group."""

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


def test_create_sends_conid_and_database(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(method="POST", url=f"{BASE}/sessions/create", json={"sesid": "s1"})
    runner = CliRunner()
    result = runner.invoke(app, ["sessions", "create", "--connection", "c1", "--database", "app"])
    assert result.exit_code == 0, result.output
    assert "s1" in result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/sessions/create")
    body = _body(req)
    assert body["conid"] == "c1"
    assert body["database"] == "app"


def test_ping_sends_sesid(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(method="POST", url=f"{BASE}/sessions/ping", json={"status": "ok"})
    runner = CliRunner()
    result = runner.invoke(app, ["sessions", "ping", "s1"])
    assert result.exit_code == 0, result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/sessions/ping")
    assert _body(req) == {"sesid": "s1"}


def test_kill_sends_sesid(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(method="POST", url=f"{BASE}/sessions/kill", json={"ok": True})
    runner = CliRunner()
    result = runner.invoke(app, ["sessions", "kill", "s1"])
    assert result.exit_code == 0, result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/sessions/kill")
    assert _body(req) == {"sesid": "s1"}
