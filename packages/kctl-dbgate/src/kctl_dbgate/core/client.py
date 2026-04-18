"""DBGate HTTP client.

DBGate exposes an RPC-style POST API on the root path (NOT under /api). Auth is:

    POST /auth/login  {"amoid": "logins", "login": ..., "password": ...}
         -> {"accessToken": "<jwt>"}

Every other call is:

    POST /<group>/<action>  (JSON body)
    Authorization: Bearer <accessToken>

The token may expire; on 401 we re-login once and retry.
"""

from __future__ import annotations

from typing import Any

import httpx
from kctl_lib.exceptions import APIError, AuthenticationError, ConfigError


class DBGateClient:
    """Synchronous HTTP client for DBGate RPC API."""

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
        """Authenticate and cache access token."""
        if not self._password:
            raise AuthenticationError("No DBGate password configured. Run: kctl-dbgate config init")
        try:
            r = self._client.post(
                "/auth/login",
                json={
                    "amoid": "logins",
                    "login": self._login,
                    "password": self._password,
                },
            )
        except httpx.HTTPError as e:
            raise APIError(detail=f"Login request failed: {e}") from e

        if r.status_code != 200:
            body = self._safe_text(r)
            raise AuthenticationError(f"Login failed ({r.status_code}): {body[:200]}")

        data = r.json() if r.content else {}
        token = data.get("accessToken")
        if not token:
            raise AuthenticationError("Login response missing accessToken")
        self._token = token
        return str(token)

    def _auth_headers(self) -> dict[str, str]:
        if self._token is None:
            self.login()
        return {"Authorization": f"Bearer {self._token or ''}"}

    # ------------------------------------------------------------------
    # Raw HTTP
    # ------------------------------------------------------------------

    def call(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        """Canonical DBGate RPC call: POST /<path> with Bearer token.

        Auto-logins if no token is cached. On 401, re-logs in once and retries.
        """
        if not path.startswith("/"):
            path = "/" + path

        if self._token is None:
            self.login()

        r = self._client.post(path, json=payload or {}, headers=self._auth_headers())
        if r.status_code == 401:
            # Token probably expired — re-auth once, retry once.
            self._token = None
            self.login()
            r = self._client.post(path, json=payload or {}, headers=self._auth_headers())
        return self._unwrap(r)

    def post(self, path: str, json: dict[str, Any] | None = None, **_: Any) -> Any:
        """Alias for call() — kept for legacy callers."""
        return self.call(path, json)

    def get(self, path: str, **_: Any) -> Any:
        """DBGate routes everything via POST; this is kept for /health-style endpoints."""
        try:
            r = self._client.get(path)
        except httpx.HTTPError as e:
            raise APIError(detail=f"GET {path} failed: {e}") from e
        return self._unwrap(r)

    @staticmethod
    def _safe_text(r: httpx.Response) -> str:
        try:
            return r.text
        except Exception:
            return ""

    @classmethod
    def _unwrap(cls, r: httpx.Response) -> Any:
        if r.status_code >= 400:
            # Try to surface apiErrorMessage if present
            try:
                data = r.json()
            except ValueError:
                data = None
            if isinstance(data, dict) and data.get("apiErrorMessage"):
                raise APIError(status_code=r.status_code, detail=str(data["apiErrorMessage"]))
            raise APIError(status_code=r.status_code, detail=cls._safe_text(r)[:200])
        if not r.content:
            return None
        try:
            data = r.json()
        except ValueError:
            return r.text
        # Some DBGate endpoints return apiErrorMessage with HTTP 200
        if isinstance(data, dict) and data.get("apiErrorMessage"):
            raise APIError(status_code=r.status_code, detail=str(data["apiErrorMessage"]))
        return data

    # ------------------------------------------------------------------
    # High-level convenience
    # ------------------------------------------------------------------

    def ping(self) -> int:
        """HTTP status of root page (no auth required)."""
        try:
            r = self._client.get("/")
            return r.status_code
        except httpx.HTTPError as e:
            raise APIError(detail=f"Ping failed: {e}") from e

    def list_connections(self) -> list[dict[str, Any]]:
        """List all registered connections."""
        result = self.call("/connections/list")
        if isinstance(result, list):
            return result
        return []
