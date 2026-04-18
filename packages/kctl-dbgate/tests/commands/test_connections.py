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
    """new-sqlite must go through /connections/save so the user-provided file
    path and label are honoured — /connections/new-sqlite-database ignores
    both and drops the db file inside DBGate's app folder.
    """
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/save",
        json={"_id": "sq1"},
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["connections", "new-sqlite", "--label", "MyLite", "--file", "/tmp/my.db"],
    )
    assert result.exit_code == 0, result.output

    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/connections/save")
    body = _body_of(req)
    assert body["displayName"] == "MyLite"
    assert body["databaseFile"] == "/tmp/my.db"
    assert body["engine"] == "sqlite@dbgate-plugin-sqlite"
    assert body.get("singleDatabase") is True


def test_new_duckdb_payload(httpx_mock: HTTPXMock) -> None:
    """Same reasoning as new-sqlite: must use /connections/save directly."""
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/save",
        json={"_id": "dk1"},
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["connections", "new-duckdb", "--label", "MyDuck", "--file", "/tmp/d.duckdb"],
    )
    assert result.exit_code == 0, result.output

    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/connections/save")
    body = _body_of(req)
    assert body["displayName"] == "MyDuck"
    assert body["databaseFile"] == "/tmp/d.duckdb"
    assert body["engine"] == "duckdb@dbgate-plugin-duckdb"


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
    # DBGate destructures {_id, values} — a flat payload is silently a no-op.
    assert body["_id"] == "a1"
    assert "values" in body, f"update must nest fields under 'values', got: {body}"
    assert body["values"]["displayName"] == "NewLabel"
    assert body["values"]["port"] == "6543"


def test_update_rejects_no_fields() -> None:
    """Updating with no field flags must error instead of silently no-op'ing."""
    runner = CliRunner()
    result = runner.invoke(app, ["connections", "update", "a1"])
    assert result.exit_code != 0
    assert "no fields" in result.output.lower() or "at least one" in result.output.lower()
