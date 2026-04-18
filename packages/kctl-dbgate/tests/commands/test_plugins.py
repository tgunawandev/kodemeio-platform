"""Tests for the plugins command group."""

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


def test_list_derives_from_connection_engines(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/list",
        json=[
            {"_id": "1", "engine": "postgres@dbgate-plugin-postgres"},
            {"_id": "2", "engine": "mysql@dbgate-plugin-mysql"},
            {"_id": "3", "engine": "postgres@dbgate-plugin-postgres"},
        ],
    )
    runner = CliRunner()
    result = runner.invoke(app, ["plugins", "list"])
    assert result.exit_code == 0, result.output
    assert "dbgate-plugin-postgres" in result.output
    assert "dbgate-plugin-mysql" in result.output


def test_install_sends_package_name(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(method="POST", url=f"{BASE}/plugins/install", json={"ok": True})
    runner = CliRunner()
    result = runner.invoke(app, ["plugins", "install", "dbgate-plugin-redis"])
    assert result.exit_code == 0, result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/plugins/install")
    assert _body(req) == {"packageName": "dbgate-plugin-redis"}


def test_uninstall_sends_package_name(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(method="POST", url=f"{BASE}/plugins/uninstall", json={"ok": True})
    runner = CliRunner()
    result = runner.invoke(app, ["plugins", "uninstall", "dbgate-plugin-redis"])
    assert result.exit_code == 0, result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/plugins/uninstall")
    assert _body(req) == {"packageName": "dbgate-plugin-redis"}


def test_upgrade_sends_package_name(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(method="POST", url=f"{BASE}/plugins/upgrade", json={"ok": True})
    runner = CliRunner()
    result = runner.invoke(app, ["plugins", "upgrade", "dbgate-plugin-redis"])
    assert result.exit_code == 0, result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/plugins/upgrade")
    assert _body(req) == {"packageName": "dbgate-plugin-redis"}
