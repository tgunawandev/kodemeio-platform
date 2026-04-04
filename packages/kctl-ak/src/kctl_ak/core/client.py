"""Authentik API client — subclasses kctl-lib APIClient."""

from __future__ import annotations

from typing import Any

import httpx
from kctl_lib.api_client import APIClient
from kctl_lib.exceptions import APIError
from kctl_lib.exceptions import ConnectionError as KctlConnectionError


class AuthentikClient(APIClient):
    """Synchronous httpx client for Authentik API v3."""

    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"
    API_PREFIX = "/api/v3"

    def __init__(self, base_url: str, credential: str, timeout: float = 30.0) -> None:
        if not base_url:
            from kctl_lib.exceptions import ConfigError

            raise ConfigError("No API URL configured. Run: kctl-ak config init")
        super().__init__(base_url=base_url, credential=credential, timeout=timeout)
        # Store root URL for health checks
        self._root_url = base_url.rstrip("/")

    def _ensure_trailing_slash(self, endpoint: str) -> str:
        url = endpoint.lstrip("/")
        if not url.endswith("/") and "?" not in url:
            url += "/"
        return url

    # Override CRUD to maintain trailing-slash and params/json API compat
    def get(self, endpoint: str, params: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        url = self._ensure_trailing_slash(endpoint)
        return super().get(url, params=params, **kwargs)

    def post(self, endpoint: str, data: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        url = self._ensure_trailing_slash(endpoint)
        return super().post(url, json=data, **kwargs)

    def patch(self, endpoint: str, data: dict[str, Any], **kwargs: Any) -> Any:
        url = self._ensure_trailing_slash(endpoint)
        return super().patch(url, json=data, **kwargs)

    def put(self, endpoint: str, data: dict[str, Any], **kwargs: Any) -> Any:
        url = self._ensure_trailing_slash(endpoint)
        return super().put(url, json=data, **kwargs)

    def delete(self, endpoint: str, **kwargs: Any) -> Any:
        url = self._ensure_trailing_slash(endpoint)
        return super().delete(url, **kwargs)

    def post_multipart(self, endpoint: str, files: dict[str, Any], data: dict[str, Any] | None = None) -> Any:
        """POST with multipart form data (for file uploads)."""
        url = self._ensure_trailing_slash(endpoint)
        headers = dict(self._client.headers)
        headers.pop("Content-Type", None)
        try:
            response = self._client.post(url, files=files, data=data, headers=headers)
        except httpx.HTTPError as e:
            raise KctlConnectionError(self._base_url, e) from e
        if response.status_code >= 400:
            detail = self._map_error(response)
            raise APIError(status_code=response.status_code, detail=detail)
        return self._unwrap_response(response)

    def patch_multipart(self, endpoint: str, files: dict[str, Any], data: dict[str, Any] | None = None) -> Any:
        """PATCH with multipart form data (for file uploads like app icons)."""
        url = self._ensure_trailing_slash(endpoint)
        headers = dict(self._client.headers)
        headers.pop("Content-Type", None)
        try:
            response = self._client.patch(url, files=files, data=data, headers=headers)
        except httpx.HTTPError as e:
            raise KctlConnectionError(self._base_url, e) from e
        if response.status_code >= 400:
            detail = self._map_error(response)
            raise APIError(status_code=response.status_code, detail=detail)
        return self._unwrap_response(response)

    def get_all(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Fetch all pages and return combined results list."""
        all_results: list[dict[str, Any]] = []
        page = 1
        p = dict(params or {})
        p.setdefault("page_size", 100)
        while True:
            p["page"] = page
            data = self.get(endpoint, params=p)
            all_results.extend(data.get("results", []))
            pagination = data.get("pagination", {})
            if not pagination.get("next"):
                break
            page += 1
            if page > 200:
                break
        return all_results

    def check_health(self, probe: str = "live") -> int:
        """Check health probe, returns HTTP status code."""
        try:
            r = httpx.get(f"{self._root_url}/-/health/{probe}/", timeout=5)
            return r.status_code
        except httpx.HTTPError:
            return 0
