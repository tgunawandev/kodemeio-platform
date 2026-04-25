"""Supabase HTTP client — communicates via Kong API gateway.

All API paths route through Kong at the base URL:
  - Auth Admin:  /auth/v1/admin/...
  - REST:        /rest/v1/...
  - Storage:     /storage/v1/...
  - Realtime:    /realtime/v1/...

Authentication uses two headers:
  - apikey: <service_role_key>  (Kong tier check)
  - Authorization: Bearer <service_role_key>  (PostgREST / GoTrue check)
"""

from __future__ import annotations

import os
import sys
from typing import Any

import httpx

from kctl_supa.core.exceptions import APIError, AuthError


class SupabaseClient:
    """Synchronous HTTP client for self-hosted Supabase via Kong."""

    def __init__(
        self,
        base_url: str,
        service_role_key: str,
        anon_key: str = "",
        timeout: float = 30.0,
    ) -> None:
        if not base_url or not base_url.strip():
            raise AuthError("No Supabase URL configured. Run: kctl-supa config init")
        if not service_role_key or not service_role_key.strip():
            raise AuthError("No service role key configured. Run: kctl-supa config init")

        self._base_url = base_url.rstrip("/")
        self._service_role_key = service_role_key
        self._anon_key = anon_key
        self._timeout = timeout

        self._headers: dict[str, str] = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
        }

        self._client = httpx.Client(
            headers=self._headers,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Core request
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Send an HTTP request, raising APIError on 4xx/5xx."""
        url = f"{self._base_url}/{path.lstrip('/')}"
        self._log_debug(f"{method.upper()} {url}")

        try:
            response = self._client.request(method, url, **kwargs)
        except httpx.ConnectError as exc:
            raise APIError(status_code=0, endpoint=url, message=str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise APIError(status_code=0, endpoint=url, message=f"Timeout: {exc}") from exc

        if response.status_code >= 400:
            message = self._extract_error(response)
            raise APIError(status_code=response.status_code, endpoint=url, message=message)

        return response

    @staticmethod
    def _extract_error(response: httpx.Response) -> str:
        """Extract a human-readable error from the response body."""
        try:
            data = response.json()
            if isinstance(data, dict):
                for key in ("message", "error_description", "error", "detail", "msg"):
                    if key in data:
                        return str(data[key])
        except (ValueError, KeyError, TypeError):
            pass
        return response.text[:200] if response.text else f"HTTP {response.status_code}"

    @staticmethod
    def _log_debug(msg: str) -> None:
        if os.environ.get("KCTL_DEBUG"):
            print(f"[DEBUG] {msg}", file=sys.stderr)  # noqa: T201

    # ------------------------------------------------------------------
    # Convenience HTTP methods
    # ------------------------------------------------------------------

    def get(self, path: str, **kwargs: Any) -> Any:
        return self._request("GET", path, **kwargs).json()

    def post(self, path: str, **kwargs: Any) -> Any:
        return self._request("POST", path, **kwargs).json()

    def put(self, path: str, **kwargs: Any) -> Any:
        return self._request("PUT", path, **kwargs).json()

    def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._request("DELETE", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> Any:
        return self._request("PATCH", path, **kwargs).json()

    # ------------------------------------------------------------------
    # Auth Admin API  (/auth/v1/admin)
    # ------------------------------------------------------------------

    def auth_list_users(self, page: int = 1, per_page: int = 50) -> Any:
        """List all users via Auth Admin API."""
        return self.get("/auth/v1/admin/users", params={"page": page, "per_page": per_page})

    def auth_get_user(self, user_id: str) -> Any:
        """Get a single user by ID."""
        return self.get(f"/auth/v1/admin/users/{user_id}")

    def auth_create_user(self, email: str, password: str, **extra: Any) -> Any:
        """Create a new user."""
        payload: dict[str, Any] = {"email": email, "password": password, **extra}
        return self.post("/auth/v1/admin/users", json=payload)

    def auth_delete_user(self, user_id: str) -> httpx.Response:
        """Delete a user by ID."""
        return self.delete(f"/auth/v1/admin/users/{user_id}")

    def auth_update_user(self, user_id: str, **fields: Any) -> Any:
        """Update a user's attributes."""
        return self.put(f"/auth/v1/admin/users/{user_id}", json=fields)

    # ------------------------------------------------------------------
    # Storage API  (/storage/v1)
    # ------------------------------------------------------------------

    def storage_list_buckets(self) -> Any:
        """List all storage buckets."""
        return self.get("/storage/v1/bucket")

    def storage_create_bucket(self, name: str, public: bool = False, **extra: Any) -> Any:
        """Create a storage bucket."""
        payload: dict[str, Any] = {"id": name, "name": name, "public": public, **extra}
        return self.post("/storage/v1/bucket", json=payload)

    def storage_delete_bucket(self, bucket_id: str) -> httpx.Response:
        """Delete a storage bucket."""
        return self.delete(f"/storage/v1/bucket/{bucket_id}")

    def storage_list_objects(self, bucket_id: str, prefix: str = "") -> Any:
        """List objects in a bucket."""
        payload: dict[str, Any] = {"prefix": prefix, "limit": 100, "offset": 0}
        return self.post(f"/storage/v1/object/list/{bucket_id}", json=payload)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> dict[str, str]:
        """Check reachability of Kong, Auth, REST, and Storage endpoints.

        Returns a dict mapping service name -> "ok" | "error: <message>".
        """
        checks: dict[str, tuple[str, str]] = {
            "kong": ("GET", "/"),
            "auth": ("GET", "/auth/v1/health"),
            "rest": ("GET", "/rest/v1/"),
            "storage": ("GET", "/storage/v1/status"),
        }
        results: dict[str, str] = {}
        for service, (method, path) in checks.items():
            try:
                self._request(method, path)
                results[service] = "ok"
            except APIError as exc:
                if exc.status_code == 401:
                    results[service] = "ok (auth required)"
                else:
                    results[service] = f"error: {exc}"
            except Exception as exc:  # noqa: BLE001
                results[service] = f"error: {exc}"
        return results

    # ------------------------------------------------------------------
    # Context manager + cleanup
    # ------------------------------------------------------------------

    def __enter__(self) -> SupabaseClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()
