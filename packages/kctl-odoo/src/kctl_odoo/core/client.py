"""Odoo JSON-RPC client using httpx.

Odoo JSON-RPC API:
- POST /jsonrpc with {jsonrpc: "2.0", method: "call", params: {service, method, args}}
- service="common", method="authenticate" → returns uid
- service="object", method="execute_kw" → ORM calls
- service="db" → database management

Note: This client uses JSON-RPC 2.0 protocol (not REST), so it does NOT
subclass kctl_lib.api_client.APIClient which is REST-oriented.
"""

from __future__ import annotations

from typing import Any

import httpx

from kctl_odoo.core.exceptions import (
    APIError,
    AuthenticationError,
    RPCError,
)
from kctl_odoo.core.exceptions import ConnectionError as KctlConnectionError


class OdooClient:
    """Synchronous httpx client for Odoo JSON-RPC."""

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
        self._client = httpx.Client(
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
    def uid(self) -> int:
        """Get authenticated user ID, authenticating if needed."""
        if self._uid is None:
            self.authenticate()
        assert self._uid is not None
        return self._uid

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    def _jsonrpc(self, url: str, params: dict) -> Any:
        """Make a JSON-RPC 2.0 call."""
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "id": self._next_id(),
            "params": params,
        }
        try:
            response = self._client.post(url, json=payload)
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

    def authenticate(self) -> int:
        """Authenticate via JSON-RPC and return uid."""
        result = self._jsonrpc(
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

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list | None = None,
        kwargs: dict | None = None,
    ) -> Any:
        """Call an ORM method via execute_kw."""
        return self._jsonrpc(
            f"{self._base_url}/jsonrpc",
            {
                "service": "object",
                "method": "execute_kw",
                "args": [
                    self._database,
                    self.uid,
                    self._api_key,
                    model,
                    method,
                    args or [],
                    kwargs or {},
                ],
            },
        )

    def search(self, model: str, domain: list | None = None, limit: int = 0, offset: int = 0) -> list[int]:
        """Search for record IDs."""
        kwargs: dict[str, Any] = {}
        if limit:
            kwargs["limit"] = limit
        if offset:
            kwargs["offset"] = offset
        return self.execute_kw(model, "search", [domain or []], kwargs)

    def search_read(
        self,
        model: str,
        domain: list | None = None,
        fields: list[str] | None = None,
        limit: int = 0,
        offset: int = 0,
        order: str = "",
    ) -> list[dict]:
        """Search and read records."""
        kwargs: dict[str, Any] = {}
        if fields:
            kwargs["fields"] = fields
        if limit:
            kwargs["limit"] = limit
        if offset:
            kwargs["offset"] = offset
        if order:
            kwargs["order"] = order
        return self.execute_kw(model, "search_read", [domain or []], kwargs)

    def read(self, model: str, ids: list[int], fields: list[str] | None = None) -> list[dict]:
        """Read specific records by ID."""
        kwargs: dict[str, Any] = {}
        if fields:
            kwargs["fields"] = fields
        return self.execute_kw(model, "read", [ids], kwargs)

    def search_count(self, model: str, domain: list | None = None) -> int:
        """Count records matching domain."""
        return self.execute_kw(model, "search_count", [domain or []])

    def create(self, model: str, vals: dict) -> int:
        """Create a record, return ID."""
        return self.execute_kw(model, "create", [vals])

    def write(self, model: str, ids: list[int], vals: dict) -> bool:
        """Update records."""
        return self.execute_kw(model, "write", [ids, vals])

    def unlink(self, model: str, ids: list[int]) -> bool:
        """Delete records."""
        return self.execute_kw(model, "unlink", [ids])

    def fields_get(self, model: str, attributes: list[str] | None = None) -> dict:
        """Get field definitions for a model."""
        kwargs: dict[str, Any] = {}
        if attributes:
            kwargs["attributes"] = attributes
        return self.execute_kw(model, "fields_get", [], kwargs)

    def db_list(self) -> list[str]:
        """List databases via database service."""
        return self._jsonrpc(
            f"{self._base_url}/jsonrpc",
            {"service": "db", "method": "list", "args": []},
        )

    def db_backup(self, database: str, backup_format: str = "zip") -> bytes:
        """Backup a database. Returns raw backup bytes."""
        # Database backup uses the web endpoint, not JSON-RPC
        response = self._client.post(
            f"{self._base_url}/web/database/backup",
            data={
                "master_pwd": self._api_key,
                "name": database,
                "backup_format": backup_format,
            },
            timeout=600,
        )
        if response.status_code != 200 or response.headers.get("content-type", "").startswith("text/html"):
            raise APIError(detail=f"Backup failed (HTTP {response.status_code})")
        return response.content

    def db_restore(self, database: str, backup_file: bytes, copy: bool = True) -> bool:
        """Restore a database from backup."""
        response = self._client.post(
            f"{self._base_url}/web/database/restore",
            data={
                "master_pwd": self._api_key,
                "name": database,
                "copy": "true" if copy else "false",
            },
            files={"backup_file": ("backup.zip", backup_file, "application/zip")},
            timeout=600,
        )
        if response.status_code != 200:
            raise APIError(detail=f"Restore failed (HTTP {response.status_code})")
        return True

    def db_duplicate(self, source: str, target: str) -> bool:
        """Duplicate a database."""
        return self._jsonrpc(
            f"{self._base_url}/jsonrpc",
            {"service": "db", "method": "duplicate_database", "args": [self._api_key, source, target]},
        )

    def db_rename(self, old_name: str, new_name: str) -> bool:
        """Rename a database."""
        return self._jsonrpc(
            f"{self._base_url}/jsonrpc",
            {"service": "db", "method": "rename", "args": [self._api_key, old_name, new_name]},
        )

    def db_exist(self, name: str) -> bool:
        """Check whether a database exists."""
        return self._jsonrpc(
            f"{self._base_url}/jsonrpc",
            {"service": "db", "method": "db_exist", "args": [name]},
        )

    def db_list_lang(self) -> list:
        """List available languages for database creation."""
        return self._jsonrpc(
            f"{self._base_url}/jsonrpc",
            {"service": "db", "method": "list_lang", "args": []},
        )

    def for_database(self, database: str) -> OdooClient:
        """Return a new client pointing at a different database on the same server."""
        return OdooClient(
            base_url=self._base_url,
            database=database,
            username=self._username,
            api_key=self._api_key,
            timeout=self._client.timeout.connect,  # preserve timeout
        )

    def db_create(self, name: str, lang: str = "en_US") -> None:
        """Create a new database via the db service."""
        self._jsonrpc(
            f"{self._base_url}/jsonrpc",
            {
                "service": "db",
                "method": "create_database",
                "args": [self._api_key, name, False, lang, self._api_key],
            },
        )

    def db_drop(self, name: str) -> None:
        """Drop a database via the db service."""
        self._jsonrpc(
            f"{self._base_url}/jsonrpc",
            {"service": "db", "method": "drop", "args": [self._api_key, name]},
        )

    def call_button(self, model: str, method: str, ids: list[int]) -> Any:
        """Convenience wrapper for button / action methods on records."""
        return self.execute_kw(model, method, [ids])

    def version_info(self) -> dict:
        """Get Odoo server version info."""
        return self._jsonrpc(
            f"{self._base_url}/jsonrpc",
            {"service": "common", "method": "version", "args": []},
        )

    def check_health(self) -> tuple[bool, str]:
        """Check if Odoo is reachable. Returns (ok, version_or_error)."""
        try:
            info = self.version_info()
            return True, info.get("server_version", "unknown")
        except Exception as e:
            return False, str(e)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OdooClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
