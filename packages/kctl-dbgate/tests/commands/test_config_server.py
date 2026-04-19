"""Tests for server-side settings commands in config group."""

from __future__ import annotations

import json
from pathlib import Path
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


def test_server_show_prints_config(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/config/get",
        json={"login": "admin", "isDocker": True, "version": "7.1.8"},
    )
    runner = CliRunner()
    result = runner.invoke(app, ["config", "server-show"])
    assert result.exit_code == 0, result.output
    assert "7.1.8" in result.output or "admin" in result.output


def test_server_set_sends_payload(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(method="POST", url=f"{BASE}/config/update-settings", json={})
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["config", "server-set", "--key", "autoRefreshInterval", "--value", "30"],
    )
    assert result.exit_code == 0, result.output
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/config/update-settings")
    body = _body(req)
    assert body["autoRefreshInterval"] == "30"


def test_server_changelog_prints(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/config/changelog",
        json="# ChangeLog\n\n## 7.1.8\n- FIXED: things",
    )
    runner = CliRunner()
    result = runner.invoke(app, ["config", "server-changelog"])
    assert result.exit_code == 0, result.output
    assert "ChangeLog" in result.output


def test_server_export_writes_yaml(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/config/get",
        json={"version": "7.1.8", "isDocker": True},
    )
    out_file = tmp_path / "cfg.yaml"
    runner = CliRunner()
    result = runner.invoke(app, ["config", "server-export", str(out_file)])
    assert result.exit_code == 0, result.output
    assert out_file.exists()
    text = out_file.read_text()
    assert "7.1.8" in text


def test_server_import_dry_run_does_not_send(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    infile = tmp_path / "cfg.yaml"
    infile.write_text("version: 7.1.8\n")
    runner = CliRunner()
    result = runner.invoke(app, ["config", "server-import", str(infile), "--dry-run"])
    assert result.exit_code == 0, result.output
    reqs = [r for r in httpx_mock.get_requests() if r.url.path == "/config/import-connections-and-settings"]
    assert len(reqs) == 0
