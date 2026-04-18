"""DBGate HTTP client.

DBGate exposes a REST API at /api/* and uses session-based auth.
Login: POST /api/auth/login  {login, password} -> {token}
Auth header: x-access-token: <token>
"""

from __future__ import annotations

from typing import Any

import httpx
from kctl_lib.exceptions import APIError, AuthenticationError, ConfigError


class DBGateClient:
    """Synchronous HTTP client for DBGate API."""

    def __init__(
        self,
        base_url: str = "",
        login: str = "",
        password: str = "",
        timeout: float = 30.0,
    ) -> None:
        if not base_url:
            raise ConfigError("No DBGate URL configured. Run: kctl-dbgate config init")
        self._base_url = base_url.rstrip("/")
        self._login = login or "admin"
        self._password = password
        self._token: str | None = None
        self._client = httpx.Client(base_url=self._base_url, timeout=timeout)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> DBGateClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def login(self) -> str:
        """Authenticate and cache session token."""
        if not self._password:
            raise AuthenticationError("No DBGate password configured. Run: kctl-dbgate config init")
        try:
            r = self._client.post(
                "/api/auth/login",
                json={"login": self._login, "password": self._password},
            )
        except httpx.HTTPError as e:
            raise APIError(f"Login request failed: {e}") from e

        if r.status_code != 200:
            raise AuthenticationError(f"Login failed ({r.status_code}): {r.text[:200]}")

        data = r.json() if r.content else {}
        token = data.get("token")
        if not token:
            raise AuthenticationError("Login response missing token")
        self._token = token
        return token

    def _auth_headers(self) -> dict[str, str]:
        if self._token is None:
            self.login()
        return {"x-access-token": self._token or ""}

    # ------------------------------------------------------------------
    # Raw HTTP
    # ------------------------------------------------------------------

    def get(self, path: str, **kwargs: Any) -> Any:
        r = self._client.get(path, headers=self._auth_headers(), **kwargs)
        return self._unwrap(r)

    def post(self, path: str, json: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        r = self._client.post(path, json=json, headers=self._auth_headers(), **kwargs)
        return self._unwrap(r)

    @staticmethod
    def _unwrap(r: httpx.Response) -> Any:
        if r.status_code >= 400:
            raise APIError(f"HTTP {r.status_code}: {r.text[:200]}")
        if not r.content:
            return None
        try:
            return r.json()
        except ValueError:
            return r.text

    # ------------------------------------------------------------------
    # High-level convenience
    # ------------------------------------------------------------------

    def ping(self) -> int:
        """HTTP status of root page (no auth required)."""
        try:
            r = self._client.get("/")
            return r.status_code
        except httpx.HTTPError as e:
            raise APIError(f"Ping failed: {e}") from e

    def list_connections(self) -> list[dict[str, Any]]:
        """List all registered connections."""
        result = self.get("/api/connections/list")
        if isinstance(result, list):
            return result
        return []
