"""Tests for the query command group."""

from __future__ import annotations

import json
from pathlib import Path
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


def test_run_sends_sql_and_prints_rows(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/database-connections/sql-select",
        json={
            "rows": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
            "columns": [{"columnName": "id"}, {"columnName": "name"}],
        },
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "run", "--connection", "c1", "--database", "app", "--sql", "SELECT * FROM users"],
    )
    assert result.exit_code == 0, result.output
    assert "Alice" in result.output
    assert "Bob" in result.output

    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/database-connections/sql-select")
    body = _body(req)
    assert body["conid"] == "c1"
    assert body["database"] == "app"
    assert body["sql"] == "SELECT * FROM users"


def test_run_from_file(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    sql_file = tmp_path / "q.sql"
    sql_file.write_text("SELECT 1")
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/database-connections/sql-select",
        json={"rows": [], "columns": []},
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "run", "--connection", "c1", "--database", "app", "--file", str(sql_file)],
    )
    assert result.exit_code == 0, result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/database-connections/sql-select")
    assert _body(req)["sql"] == "SELECT 1"


def test_run_var_substitution(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/database-connections/sql-select",
        json={"rows": [], "columns": []},
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            "run",
            "--connection",
            "c1",
            "--database",
            "app",
            "--sql",
            "SELECT * FROM {{t}}",
            "--var",
            "t=users",
        ],
    )
    assert result.exit_code == 0, result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/database-connections/sql-select")
    assert _body(req)["sql"] == "SELECT * FROM users"


def test_select_builds_query(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/database-connections/sql-select",
        json={"rows": [], "columns": []},
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            "select",
            "--connection",
            "c1",
            "--database",
            "app",
            "--table",
            "u",
            "--limit",
            "10",
            "--where",
            "x=1",
        ],
    )
    assert result.exit_code == 0, result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/database-connections/sql-select")
    sql = _body(req)["sql"]
    assert "SELECT" in sql.upper()
    assert "u" in sql  # table name
    assert "x=1" in sql
    assert "10" in sql


def test_preview_does_not_execute(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/database-connections/sql-preview",
        json={"sql": "SELECT * FROM users", "errorMessage": None},
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "preview", "--connection", "c1", "--database", "app", "--sql", "SELECT * FROM users"],
    )
    assert result.exit_code == 0, result.output
    assert "SELECT" in result.output
    # No sql-select was called
    selects = [r for r in httpx_mock.get_requests() if r.url.path == "/database-connections/sql-select"]
    assert len(selects) == 0


def test_eval_requires_script_file(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    runner = CliRunner()
    missing = tmp_path / "nope.js"
    result = runner.invoke(
        app,
        ["query", "eval", "--connection", "c1", "--database", "app", "--script", str(missing)],
    )
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "no such" in result.output.lower()


def test_eval_sends_script_contents(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    _mock_login(httpx_mock)
    script = tmp_path / "s.js"
    script.write_text("db.getCollection('x').find()")
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/database-connections/eval-json-script",
        json={"rows": [], "columns": []},
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "eval", "--connection", "c1", "--database", "app", "--script", str(script)],
    )
    assert result.exit_code == 0, result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/database-connections/eval-json-script")
    body = _body(req)
    assert body["conid"] == "c1"
    assert body["database"] == "app"
    assert "db.getCollection" in body["script"]


def test_format_csv_emits_csv(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/database-connections/sql-select",
        json={
            "rows": [{"id": 1, "name": "Alice"}],
            "columns": [{"columnName": "id"}, {"columnName": "name"}],
        },
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--format",
            "csv",
            "query",
            "run",
            "--connection",
            "c1",
            "--database",
            "app",
            "--sql",
            "SELECT 1",
        ],
    )
    assert result.exit_code == 0, result.output
    # CSV has no pretty-print borders
    assert "│" not in result.output
    assert "id" in result.output
    assert "Alice" in result.output
