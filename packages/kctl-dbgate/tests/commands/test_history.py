"""Tests for the history command group."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from kctl_dbgate.cli import app

BASE = "https://dbgate.example.com"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KCTL_DBGATE_URL", BASE)
    monkeypatch.setenv("KCTL_DBGATE_LOGIN", "admin")
    monkeypatch.setenv("KCTL_DBGATE_PASSWORD", "hunter2")


def _mock_login(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="POST", url=f"{BASE}/auth/login", json={"accessToken": "tok"})


def _body(req: Any) -> dict[str, Any]:
    return json.loads(req.content)  # type: ignore[no-any-return]


def test_list_prints_history(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/query-history/read",
        json=[
            {"conid": "c1", "database": "app", "sql": "SELECT 1", "date": "2026-01-01"},
            {"conid": "c2", "database": "app", "sql": "SELECT 2", "date": "2026-01-02"},
        ],
    )
    runner = CliRunner()
    result = runner.invoke(app, ["history", "list"])
    assert result.exit_code == 0, result.output
    assert "SELECT 1" in result.output
    assert "SELECT 2" in result.output


def test_add_sends_sql(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(method="POST", url=f"{BASE}/query-history/write", json="OK")
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["history", "add", "--connection", "c1", "--sql", "SELECT now()", "--database", "app"],
    )
    assert result.exit_code == 0, result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/query-history/write")
    body = _body(req)
    assert body["conid"] == "c1"
    assert body["sql"] == "SELECT now()"
    assert body["database"] == "app"
