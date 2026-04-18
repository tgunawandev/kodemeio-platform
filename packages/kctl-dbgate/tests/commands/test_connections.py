"""Tests for the connections command group."""

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
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/auth/login",
        json={"accessToken": "tok"},
    )


def _body_of(req: Any) -> dict[str, Any]:
    return json.loads(req.content)  # type: ignore[no-any-return]


def test_list_prints_table(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/list",
        json=[
            {
                "_id": "a1",
                "displayName": "Alpha",
                "engine": "postgres@dbgate-plugin-postgres",
                "server": "db1",
                "port": 5432,
                "user": "u1",
            },
            {
                "_id": "b2",
                "displayName": "Beta",
                "engine": "mysql@dbgate-plugin-mysql",
                "server": "db2",
                "port": 3306,
                "user": "u2",
                "isReadOnly": True,
            },
        ],
    )
    runner = CliRunner()
    result = runner.invoke(app, ["connections", "list"])
    assert result.exit_code == 0, result.output
    assert "Alpha" in result.output
    assert "Beta" in result.output


def test_get_prints_detail(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/get",
        json={
            "_id": "a1",
            "displayName": "Alpha",
            "engine": "postgres@dbgate-plugin-postgres",
            "server": "db1",
            "port": 5432,
            "user": "u1",
        },
    )
    runner = CliRunner()
    result = runner.invoke(app, ["connections", "get", "a1"])
    assert result.exit_code == 0, result.output
    assert "Alpha" in result.output
    assert "db1" in result.output

    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/connections/get")
    assert _body_of(req) == {"conid": "a1"}


def test_test_reports_ok_on_connected(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/test",
        json={"msgtype": "connected", "version": "16.0"},
    )
    runner = CliRunner()
    result = runner.invoke(app, ["connections", "test", "a1"])
    assert result.exit_code == 0, result.output
    assert "connected" in result.output.lower() or "OK" in result.output


def test_create_sends_correct_payload(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/save",
        json={"_id": "new1"},
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "connections",
            "create",
            "--label",
            "MyDB",
            "--engine",
            "postgres@dbgate-plugin-postgres",
            "--server",
            "db.example.com",
            "--port",
            "5432",
            "--user",
            "postgres",
            "--password",
            "secret",
            "--database",
            "mydb",
        ],
    )
    assert result.exit_code == 0, result.output

    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/connections/save")
    body = _body_of(req)
    assert body["displayName"] == "MyDB"
    assert body["engine"] == "postgres@dbgate-plugin-postgres"
    assert body["server"] == "db.example.com"
    assert body["port"] == "5432"
    assert body["user"] == "postgres"
    assert body["password"] == "secret"
    assert body["database"] == "mydb"


def test_delete_confirms_by_default(httpx_mock: HTTPXMock) -> None:
    # No mocks at all — aborting before confirm means no HTTP traffic at all.
    runner = CliRunner()
    result = runner.invoke(app, ["connections", "delete", "a1"], input="n\n")
    # Exited non-failure after aborting.
    assert result.exit_code == 0
    delete_reqs = [r for r in httpx_mock.get_requests() if r.url.path == "/connections/delete"]
    assert len(delete_reqs) == 0


def test_delete_force_skips_confirm(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/delete",
        json={"_id": "a1"},
    )
    runner = CliRunner()
    result = runner.invoke(app, ["connections", "delete", "a1", "--force"])
    assert result.exit_code == 0, result.output

    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/connections/delete")
    assert _body_of(req) == {"_id": "a1"}


def test_new_sqlite_payload(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/new-sqlite-database",
        json={"_id": "sq1"},
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["connections", "new-sqlite", "--label", "MyLite", "--file", "/tmp/my.db"],
    )
    assert result.exit_code == 0, result.output

    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/connections/new-sqlite-database")
    body = _body_of(req)
    assert body["displayName"] == "MyLite"
    assert body["databaseFile"] == "/tmp/my.db"
    assert body["engine"] == "sqlite@dbgate-plugin-sqlite"


def test_update_sends_id_and_fields(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/update",
        json={"_id": "a1"},
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["connections", "update", "a1", "--label", "NewLabel", "--port", "6543"],
    )
    assert result.exit_code == 0, result.output

    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/connections/update")
    body = _body_of(req)
    assert body["_id"] == "a1"
    assert body["displayName"] == "NewLabel"
    assert body["port"] == "6543"
