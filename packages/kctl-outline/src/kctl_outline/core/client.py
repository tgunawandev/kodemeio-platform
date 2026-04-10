"""Outline API client using httpx.

Outline API: all endpoints are POST to /api/{resource}.{action}.
Auth: Bearer token. Pagination: offset+limit.
Response: {"data": [...], "pagination": {"total": N, "offset": N, "limit": N}}.

# KCTL-COMMON: extractable (base APIClient class)
"""

from __future__ import annotations

import httpx

from kctl_outline.core.exceptions import APIError, AuthenticationError
from kctl_outline.core.exceptions import ConnectionError as KctlConnectionError


class OutlineClient:
    """Synchronous httpx client for Outline API."""

    def __init__(self, base_url: str, token: str, timeout: float = 30.0):
        if not base_url:
            raise KctlConnectionError(
                "(not configured)",
                ValueError("No API URL configured. Run: kctl-outline config init"),
            )
        if not token:
            raise AuthenticationError("No API token configured. Run: kctl-outline config init")

        self._base_url = base_url.rstrip("/")
        self._api_url = self._base_url + "/api"

        self._client = httpx.Client(
            base_url=self._api_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=timeout,
            follow_redirects=True,
        )

    def request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Make a request, raise APIError on non-2xx."""
        url = endpoint.lstrip("/")
        try:
            response = self._client.request(method, url, **kwargs)
        except httpx.ConnectError as e:
            raise KctlConnectionError(self._api_url, e) from e
        except httpx.HTTPError as e:
            raise KctlConnectionError(self._api_url, e) from e

        if response.status_code == 401:
            raise AuthenticationError("Token invalid/expired. Check your API token.")
        if response.status_code == 403:
            raise AuthenticationError("Permission denied. Check token permissions.")
        if response.status_code >= 400:
            raise APIError(response)
        return response

    def post(self, endpoint: str, data: dict | None = None) -> dict:
        """POST request (Outline API uses POST for everything)."""
        resp = self.request("POST", endpoint, json=data or {})
        if not resp.content:
            return {}
        return resp.json()

    def post_all(self, endpoint: str, params: dict | None = None) -> list[dict]:
        """Fetch all pages using offset+limit pagination."""
        all_results: list[dict] = []
        p = dict(params or {})
        p.setdefault("limit", 100)
        p.setdefault("offset", 0)
        while True:
            result = self.post(endpoint, data=p)
            data = result.get("data", [])
            if isinstance(data, list):
                all_results.extend(data)
            pagination = result.get("pagination", {})
            total = pagination.get("total", 0)
            if p["offset"] + p["limit"] >= total:
                break
            p["offset"] += p["limit"]
            if p["offset"] > 10000:
                break
        return all_results

    def check_health(self) -> int:
        """Check health, returns HTTP status code."""
        try:
            r = httpx.get(f"{self._base_url}/_health", timeout=5)
            return r.status_code
        except httpx.HTTPError:
            return 0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OutlineClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
