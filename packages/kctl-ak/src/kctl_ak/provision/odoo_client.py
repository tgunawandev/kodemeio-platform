"""Lightweight Odoo JSON-RPC client for provisioning operations only.

Only supports: check user exists, create portal user, activate/deactivate.
For full Odoo management use kctl-odoo.
"""

from __future__ import annotations

from typing import Any

import httpx


class OdooProvisionClient:
    """Minimal Odoo JSON-RPC client for provisioning chain."""

    def __init__(
        self,
        base_url: str,
        database: str,
        username: str = "admin",
        api_key: str = "",
        timeout: float = 15.0,
        _transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._database = database
        self._username = username
        self._api_key = api_key
        self._uid: int | None = None
        self._rpc_id = 0
        kwargs: dict[str, Any] = {
            "headers": {"Content-Type": "application/json"},
            "timeout": timeout,
        }
        if _transport is not None:
            kwargs["transport"] = _transport
        self._client = httpx.Client(**kwargs)

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    def _jsonrpc(self, url: str, params: dict[str, Any]) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "id": self._next_id(),
            "params": params,
        }
        resp = self._client.post(url, json=payload)
        data = resp.json()
        if "error" in data:
            msg = data["error"].get("data", {}).get("message", str(data["error"]))
            raise RuntimeError(f"Odoo RPC error: {msg}")
        return data.get("result")

    def _authenticate(self) -> int:
        if self._uid is not None:
            return self._uid
        self._uid = self._jsonrpc(
            f"{self._base_url}/jsonrpc",
            {
                "service": "common",
                "method": "authenticate",
                "args": [self._database, self._username, self._api_key, {}],
            },
        )
        if not self._uid:
            raise RuntimeError(f"Odoo authentication failed for {self._username}")
        return self._uid

    def _execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        uid = self._authenticate()
        return self._jsonrpc(
            f"{self._base_url}/jsonrpc",
            {
                "service": "object",
                "method": "execute_kw",
                "args": [self._database, uid, self._api_key, model, method, args, kwargs or {}],
            },
        )

    def user_exists(self, email: str) -> bool:
        """Check if a res.users record with this login exists."""
        results = self._execute_kw(
            "res.users",
            "search_read",
            [[["login", "=", email]]],
            {"fields": ["id", "login", "active"], "limit": 1},
        )
        return bool(results)

    def get_user(self, email: str) -> dict[str, Any] | None:
        """Get user by login email, or None."""
        results = self._execute_kw(
            "res.users",
            "search_read",
            [[["login", "=", email]]],
            {"fields": ["id", "login", "name", "active"], "limit": 1},
        )
        return results[0] if results else None

    def create_portal_user(self, email: str, name: str) -> int:
        """Create a portal user with OAuth login."""
        return self._execute_kw(
            "res.users",
            "create",
            [
                {
                    "login": email,
                    "name": name,
                    "email": email,
                    "active": True,
                    "sel_groups_1_10_11": 10,  # Portal user group (standard Odoo)
                }
            ],
        )

    def deactivate_user(self, email: str) -> bool:
        """Set user active=False by login email."""
        user = self.get_user(email)
        if not user:
            return False
        return self._execute_kw("res.users", "write", [[user["id"]], {"active": False}])

    def activate_user(self, email: str) -> bool:
        """Set user active=True by login email."""
        user = self.get_user(email)
        if not user:
            return False
        return self._execute_kw("res.users", "write", [[user["id"]], {"active": True}])
