"""Tests for GatewayClient — HTTP client for OpenClaw gateway API."""

from __future__ import annotations

import pytest

from kctl_claw.core.exceptions import GatewayError
from kctl_claw.core.gateway_client import GatewayClient


def test_health_success(httpx_mock):
    httpx_mock.add_response(
        url="https://openclaw.test/",
        json={"status": "ok", "version": "2026.3.24"},
    )
    client = GatewayClient(base_url="https://openclaw.test", token="test-token")
    result = client.health()
    assert result["status"] == "ok"


def test_health_auth_failure(httpx_mock):
    httpx_mock.add_response(
        url="https://openclaw.test/",
        status_code=401,
    )
    client = GatewayClient(base_url="https://openclaw.test", token="bad-token")
    with pytest.raises(GatewayError) as exc_info:
        client.health()
    assert exc_info.value.status_code == 401


def test_health_connection_error(httpx_mock):
    httpx_mock.add_exception(ConnectionError("refused"))
    client = GatewayClient(base_url="https://openclaw.test", token="test-token")
    with pytest.raises(GatewayError):
        client.health()


def test_get_with_params(httpx_mock):
    httpx_mock.add_response(
        url="https://openclaw.test/api/agents",
        json={"agents": ["kodemeiodev"]},
    )
    client = GatewayClient(base_url="https://openclaw.test", token="test-token")
    result = client.get("/api/agents")
    assert "agents" in result


def test_post_returns_json(httpx_mock):
    httpx_mock.add_response(
        url="https://openclaw.test/api/reload",
        json={"reloaded": True},
    )
    client = GatewayClient(base_url="https://openclaw.test", token="test-token")
    result = client.post("/api/reload", data={"force": True})
    assert result["reloaded"] is True


def test_close():
    """close() should not raise."""
    client = GatewayClient(base_url="https://openclaw.test", token="test-token")
    client.close()


def test_context_manager(httpx_mock):
    httpx_mock.add_response(
        url="https://openclaw.test/",
        json={"status": "ok"},
    )
    with GatewayClient(base_url="https://openclaw.test", token="test-token") as client:
        result = client.health()
    assert result["status"] == "ok"
