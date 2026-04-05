"""Tests for lightweight Odoo JSON-RPC client."""

from __future__ import annotations

import json
from typing import Any

import pytest
import httpx

from kctl_ak.provision.odoo_client import OdooProvisionClient


def _make_rpc_handler(responses: dict[str, Any]) -> httpx.MockTransport:
    """Create a mock transport that returns different responses based on RPC method+args."""
    call_count = {"search_read": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        params = body.get("params", {})
        service = params.get("service", "")
        method = params.get("method", "")
        args = params.get("args", [])

        # authenticate
        if service == "common" and method == "authenticate":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": 2})

        # execute_kw
        if service == "object" and method == "execute_kw":
            model = args[3] if len(args) > 3 else ""
            orm_method = args[4] if len(args) > 4 else ""

            if model == "res.users" and orm_method == "search_read":
                key = f"search_read_{call_count['search_read']}"
                call_count["search_read"] += 1
                return httpx.Response(
                    200,
                    json={
                        "jsonrpc": "2.0",
                        "id": body["id"],
                        "result": responses.get(key, []),
                    },
                )

            if model == "res.users" and orm_method == "create":
                return httpx.Response(
                    200,
                    json={
                        "jsonrpc": "2.0",
                        "id": body["id"],
                        "result": responses.get("create", 42),
                    },
                )

            if model == "res.users" and orm_method == "write":
                return httpx.Response(
                    200,
                    json={
                        "jsonrpc": "2.0",
                        "id": body["id"],
                        "result": True,
                    },
                )

        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": None})

    return httpx.MockTransport(handler)


@pytest.fixture
def client_user_not_found() -> OdooProvisionClient:
    transport = _make_rpc_handler({"search_read_0": []})
    return OdooProvisionClient(
        base_url="https://mac-odoo-dist.mandiriagro.com",
        database="mac_dist",
        username="admin",
        api_key="test-key",
        _transport=transport,
    )


@pytest.fixture
def client_user_exists() -> OdooProvisionClient:
    transport = _make_rpc_handler(
        {
            "search_read_0": [{"id": 10, "login": "john@mandiriagro.com", "active": True}],
        }
    )
    return OdooProvisionClient(
        base_url="https://mac-odoo-dist.mandiriagro.com",
        database="mac_dist",
        username="admin",
        api_key="test-key",
        _transport=transport,
    )


def test_user_exists_false(client_user_not_found: OdooProvisionClient) -> None:
    assert client_user_not_found.user_exists("john@mandiriagro.com") is False


def test_user_exists_true(client_user_exists: OdooProvisionClient) -> None:
    assert client_user_exists.user_exists("john@mandiriagro.com") is True


def test_create_portal_user(client_user_not_found: OdooProvisionClient) -> None:
    uid = client_user_not_found.create_portal_user(
        email="john@mandiriagro.com",
        name="John Doe",
    )
    assert uid == 42


def test_deactivate_user(client_user_exists: OdooProvisionClient) -> None:
    result = client_user_exists.deactivate_user("john@mandiriagro.com")
    assert result is True


def test_activate_user(client_user_exists: OdooProvisionClient) -> None:
    result = client_user_exists.activate_user("john@mandiriagro.com")
    assert result is True
