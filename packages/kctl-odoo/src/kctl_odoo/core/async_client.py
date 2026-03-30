"""Async Odoo JSON-RPC client using httpx.

Mirror of :class:`kctl_odoo.core.client.OdooClient` with ``async`` methods
and :class:`httpx.AsyncClient` under the hood.

Note: This client uses JSON-RPC 2.0 protocol (not REST), so it does NOT
subclass kctl_common.api_client.APIClient which is REST-oriented.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from kctl_odoo.core.exceptions import (
    APIError,
    AuthenticationError,
    RPCError,
)
from kctl_odoo.core.exceptions import ConnectionError as KctlConnectionError


class AsyncOdooClient:
    """Asynchronous httpx client for Odoo JSON-RPC."""

    def __init__(
        self,
        base_url: str,
        database: str,
        username: str = "admin",
        api_key: str = "",
        timeout: float = 30.0,
    ):
        if not base_url:
            raise KctlConnectionError(
                "(not configured)",
                ValueError("No Odoo URL configured. Run: kctl-odoo config init"),
            )
        if not api_key:
            raise AuthenticationError("No API key configured. Run: kctl-odoo config init")

        self._base_url = base_url.rstrip("/")
        self._database = database
        self._username = username
        self._api_key = api_key
        self._uid: int | None = None
        self._rpc_id = 0
        self._client = httpx.AsyncClient(
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=timeout,
            follow_redirects=True,
        )

    @property
    def database(self) -> str:
        return self._database

    @property
    def uid(self) -> int | None:
        """Return the cached uid (may be ``None`` before :meth:`authenticate`)."""
        return self._uid

    async def ensure_uid(self) -> int:
        """Return the authenticated uid, calling :meth:`authenticate` if needed."""
        if self._uid is None:
            await self.authenticate()
        assert self._uid is not None
        return self._uid

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    async def _jsonrpc(self, url: str, params: dict) -> Any:
        """Make a JSON-RPC 2.0 call."""
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "id": self._next_id(),
            "params": params,
        }
        try:
            response = await self._client.post(url, json=payload)
        except httpx.ConnectError as e:
            raise KctlConnectionError(self._base_url, e) from e
        except httpx.HTTPError as e:
            raise KctlConnectionError(self._base_url, e) from e

        if response.status_code >= 400:
            raise APIError(response)

        body = response.json()
        if "error" in body:
            error_data = body["error"]
            msg = error_data.get("message", "")
            if "Access Denied" in msg or "AccessDenied" in str(error_data):
                raise AuthenticationError(f"Access denied: {msg}")
            raise RPCError(error_data)

        return body.get("result")

    async def authenticate(self) -> int:
        """Authenticate via JSON-RPC and return uid."""
        result = await self._jsonrpc(
            f"{self._base_url}/jsonrpc",
            {
                "service": "common",
                "method": "authenticate",
                "args": [self._database, self._username, self._api_key, {}],
            },
        )
        if not result:
            raise AuthenticationError(
                f"Authentication failed for {self._username}@{self._database}. "
                "Check database name, username, and API key."
            )
        self._uid = int(result)
        return self._uid

    async def execute_kw(
        self,
        model: str,
        method: str,
        args: list | None = None,
        kwargs: dict | None = None,
    ) -> Any:
        """Call an ORM method via execute_kw."""
        uid = await self.ensure_uid()
        return await self._jsonrpc(
            f"{self._base_url}/jsonrpc",
            {
                "service": "object",
                "method": "execute_kw",
                "args": [
                    self._database,
                    uid,
                    self._api_key,
                    model,
                    method,
                    args or [],
                    kwargs or {},
                ],
            },
        )

    async def search(self, model: str, domain: list | None = None, limit: int = 0, offset: int = 0) -> list[int]:
        """Search for record IDs."""
        kw: dict[str, Any] = {}
        if limit:
            kw["limit"] = limit
        if offset:
            kw["offset"] = offset
        return await self.execute_kw(model, "search", [domain or []], kw)

    async def search_read(
        self,
        model: str,
        domain: list | None = None,
        fields: list[str] | None = None,
        limit: int = 0,
        offset: int = 0,
        order: str = "",
    ) -> list[dict]:
        """Search and read records."""
        kw: dict[str, Any] = {}
        if fields:
            kw["fields"] = fields
        if limit:
            kw["limit"] = limit
        if offset:
            kw["offset"] = offset
        if order:
            kw["order"] = order
        return await self.execute_kw(model, "search_read", [domain or []], kw)

    async def read(self, model: str, ids: list[int], fields: list[str] | None = None) -> list[dict]:
        """Read specific records by ID."""
        kw: dict[str, Any] = {}
        if fields:
            kw["fields"] = fields
        return await self.execute_kw(model, "read", [ids], kw)

    async def search_count(self, model: str, domain: list | None = None) -> int:
        """Count records matching domain."""
        return await self.execute_kw(model, "search_count", [domain or []])

    async def create(self, model: str, vals: dict) -> int:
        """Create a record, return ID."""
        return await self.execute_kw(model, "create", [vals])

    async def write(self, model: str, ids: list[int], vals: dict) -> bool:
        """Update records."""
        return await self.execute_kw(model, "write", [ids, vals])

    async def unlink(self, model: str, ids: list[int]) -> bool:
        """Delete records."""
        return await self.execute_kw(model, "unlink", [ids])

    async def fields_get(self, model: str, attributes: list[str] | None = None) -> dict:
        """Get field definitions for a model."""
        kw: dict[str, Any] = {}
        if attributes:
            kw["attributes"] = attributes
        return await self.execute_kw(model, "fields_get", [], kw)

    async def db_list(self) -> list[str]:
        """List databases via database service."""
        return await self._jsonrpc(
            f"{self._base_url}/jsonrpc",
            {"service": "db", "method": "list", "args": []},
        )

    async def db_exist(self, name: str) -> bool:
        """Check whether a database exists."""
        return await self._jsonrpc(
            f"{self._base_url}/jsonrpc",
            {"service": "db", "method": "db_exist", "args": [name]},
        )

    async def version_info(self) -> dict:
        """Get Odoo server version info."""
        return await self._jsonrpc(
            f"{self._base_url}/jsonrpc",
            {"service": "common", "method": "version", "args": []},
        )

    async def check_health(self) -> tuple[bool, str]:
        """Check if Odoo is reachable. Returns (ok, version_or_error)."""
        try:
            info = await self.version_info()
            return True, info.get("server_version", "unknown")
        except Exception as e:
            return False, str(e)

    async def call_button(self, model: str, method: str, ids: list[int]) -> Any:
        """Convenience wrapper for button / action methods on records."""
        return await self.execute_kw(model, method, [ids])

    def for_database(self, database: str) -> AsyncOdooClient:
        """Return a new async client pointing at a different database."""
        return AsyncOdooClient(
            base_url=self._base_url,
            database=database,
            username=self._username,
            api_key=self._api_key,
            timeout=self._client.timeout.connect or 30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AsyncOdooClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()


async def async_batch(*coroutines: Any, max_concurrent: int = 10) -> list[Any]:
    """Run multiple async operations with a concurrency limit.

    Example::

        results = await async_batch(
            client.search_read("res.partner", limit=10),
            client.search_read("sale.order", limit=10),
            max_concurrent=5,
        )
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def bounded(coro: Any) -> Any:
        async with semaphore:
            return await coro

    return list(await asyncio.gather(*(bounded(c) for c in coroutines)))
