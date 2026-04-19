"""Tests for the servers command group (server-connections/*)."""

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


def test_ping_sends_conid_array(httpx_mock: HTTPXMock) -> None:
    """DBGate expects {conidArray, strmid} — not a bare {conid}."""
    _mock_login(httpx_mock)
    httpx_mock.add_response(method="POST", url=f"{BASE}/server-connections/ping", json={"status": "ok"})
    runner = CliRunner()
    result = runner.invoke(app, ["servers", "ping", "a1"])
    assert result.exit_code == 0, result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/server-connections/ping")
    body = _body(req)
    assert body["conidArray"] == ["a1"], f"must send conidArray, got: {body}"
    assert "strmid" in body, f"must send strmid, got: {body}"


def test_summary_prints(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/server-connections/server-summary",
        json=[{"name": "db1"}, {"name": "db2"}],
    )
    runner = CliRunner()
    result = runner.invoke(app, ["servers", "summary", "a1"])
    assert result.exit_code == 0, result.output
    assert "db1" in result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/server-connections/server-summary")
    assert _body(req) == {"conid": "a1"}


def test_create_database_payload(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(method="POST", url=f"{BASE}/server-connections/create-database", json={"ok": True})
    runner = CliRunner()
    result = runner.invoke(app, ["servers", "create-database", "a1", "--name", "newdb"])
    assert result.exit_code == 0, result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/server-connections/create-database")
    body = _body(req)
    assert body["conid"] == "a1"
    assert body["name"] == "newdb"


def test_drop_database_requires_confirm(httpx_mock: HTTPXMock) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["servers", "drop-database", "a1", "--name", "bad"], input="n\n")
    assert result.exit_code == 0
    drop_reqs = [r for r in httpx_mock.get_requests() if r.url.path == "/server-connections/drop-database"]
    assert len(drop_reqs) == 0


def test_drop_database_force(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(method="POST", url=f"{BASE}/server-connections/drop-database", json={"ok": True})
    runner = CliRunner()
    result = runner.invoke(app, ["servers", "drop-database", "a1", "--name", "old", "--force"])
    assert result.exit_code == 0, result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/server-connections/drop-database")
    body = _body(req)
    assert body["conid"] == "a1"
    assert body["name"] == "old"


def test_refresh_payload(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(method="POST", url=f"{BASE}/server-connections/refresh", json={"ok": True})
    runner = CliRunner()
    result = runner.invoke(app, ["servers", "refresh", "a1"])
    assert result.exit_code == 0, result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/server-connections/refresh")
    assert _body(req) == {"conid": "a1"}


def test_disconnect_payload(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(method="POST", url=f"{BASE}/server-connections/disconnect", json={"ok": True})
    runner = CliRunner()
    result = runner.invoke(app, ["servers", "disconnect", "a1"])
    assert result.exit_code == 0, result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/server-connections/disconnect")
    assert _body(req) == {"conid": "a1"}
