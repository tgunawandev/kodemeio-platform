"""Gatus API client — uses kctl-lib exceptions.

Gatus authentication is optional (may use OIDC or reverse proxy auth),
so this client does not require a credential at init time.
"""

from __future__ import annotations

from typing import Any

import httpx
from kctl_lib.exceptions import APIError, AuthenticationError
from kctl_lib.exceptions import ConnectionError as KctlConnectionError


class GatusClient:
    """Synchronous httpx client for Gatus REST API."""

    def __init__(self, base_url: str, api_key: str = "", timeout: float = 30.0) -> None:
        if not base_url:
            from kctl_lib.exceptions import ConfigError

            raise ConfigError("No API URL configured. Run: kctl-gatus config init")

        self._base_url = base_url.rstrip("/")
        self._api_url = self._base_url + "/api/v1"

        headers: dict[str, str] = {
            "Accept": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self._client = httpx.Client(
            base_url=self._api_url,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )

    @property
    def base_url(self) -> str:
        return self._base_url

    def request(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
        """Make a request, raise APIError on non-2xx."""
        url = endpoint.lstrip("/")
        try:
            response = self._client.request(method, url, **kwargs)
        except httpx.ConnectError as e:
            raise KctlConnectionError(self._api_url, e) from e
        except httpx.HTTPError as e:
            raise KctlConnectionError(self._api_url, e) from e

        if response.status_code == 401:
            raise AuthenticationError("Authentication required. Check your API key.")
        if response.status_code == 403:
            raise AuthenticationError("Permission denied. Check API key permissions.")
        if response.status_code >= 400:
            detail = response.text[:200] if response.text else f"HTTP {response.status_code}"
            raise APIError(status_code=response.status_code, detail=detail)
        return response

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        resp = self.request("GET", endpoint, params=params)
        if not resp.content:
            return {}
        return resp.json()  # type: ignore[no-any-return]

    def get_list(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """GET that always returns a list."""
        result = self.get(endpoint, params=params)
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "results" in result:
            return result["results"]  # type: ignore[no-any-return]
        return []

    # --- Gatus-specific API methods ---

    def get_endpoint_statuses(self) -> list[dict[str, Any]]:
        """GET /api/v1/endpoints/statuses — List all endpoint statuses."""
        return self.get_list("endpoints/statuses")

    def get_endpoint_status(self, key: str) -> dict[str, Any]:
        """GET /api/v1/endpoints/{key}/statuses — Get specific endpoint status."""
        result = self.get(f"endpoints/{key}/statuses")
        if isinstance(result, dict):
            return result
        return {}

    def get_endpoint_uptimes(self, key: str, duration: str = "7d") -> dict[str, Any]:
        """GET /api/v1/endpoints/{key}/uptimes/{duration} — Get uptime data."""
        result = self.get(f"endpoints/{key}/uptimes/{duration}")
        if isinstance(result, dict):
            return result
        return {}

    def get_endpoint_response_times(self, key: str, duration: str = "7d") -> dict[str, Any]:
        """GET /api/v1/endpoints/{key}/response-times/{duration} — Get response time data."""
        result = self.get(f"endpoints/{key}/response-times/{duration}")
        if isinstance(result, dict):
            return result
        return {}

    def check_health(self) -> int:
        """Check Gatus health endpoint, returns HTTP status code."""
        try:
            r = httpx.get(f"{self._base_url}/health", timeout=5)
            return r.status_code
        except httpx.HTTPError:
            return 0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GatusClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
