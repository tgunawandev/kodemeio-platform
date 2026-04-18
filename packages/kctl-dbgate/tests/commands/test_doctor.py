"""Tests for doctor checks (ServerSummaryCheck, ConfigReadCheck)."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from kctl_dbgate.commands.doctor_cmd import ConfigReadCheck, ServerSummaryCheck

BASE = "https://dbgate.example.com"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    monkeypatch.setenv("KCTL_DBGATE_URL", BASE)
    monkeypatch.setenv("KCTL_DBGATE_LOGIN", "admin")
    monkeypatch.setenv("KCTL_DBGATE_PASSWORD", "hunter2")
    # Force an empty config so profile resolution uses env vars.
    monkeypatch.setattr(
        "kctl_dbgate.core.config.get_service_config",
        lambda _p: __import__("kctl_dbgate.core.config", fromlist=["ServiceConfig"]).ServiceConfig(
            url=BASE, login="admin", password="hunter2"
        ),
    )


def _mock_login(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="POST", url=f"{BASE}/auth/login", json={"accessToken": "tok"})


def test_config_read_check_ok(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/config/get",
        json={"version": "7.1.8", "isDocker": True},
    )
    check = ConfigReadCheck()
    result = check.run()
    assert result.status == "ok"
    assert "7.1.8" in result.message


def test_config_read_check_fail_on_error(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/config/get",
        status_code=500,
        json={"apiErrorMessage": "boom"},
    )
    check = ConfigReadCheck()
    result = check.run()
    assert result.status == "fail"
    assert "boom" in result.message


def test_server_summary_check_skip_without_connections(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(method="POST", url=f"{BASE}/connections/list", json=[])
    check = ServerSummaryCheck()
    result = check.run()
    assert result.status == "skip"


def test_server_summary_check_ok_with_connection(httpx_mock: HTTPXMock) -> None:
    _mock_login(httpx_mock)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/connections/list",
        json=[{"_id": "c1"}],
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/server-connections/server-summary",
        json=[{"name": "db1"}],
    )
    check = ServerSummaryCheck()
    result = check.run()
    assert result.status == "ok"
