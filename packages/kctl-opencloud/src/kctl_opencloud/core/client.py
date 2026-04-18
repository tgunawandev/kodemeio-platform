"""OpenCloud API client — subclasses kctl-lib APIClient.

Uses the LibreGraph REST API at /graph/v1.0.
Pagination uses OData-style @odata.nextLink.
"""

from __future__ import annotations

from typing import Any

import httpx
from kctl_lib.api_client import APIClient


class OpenCloudClient(APIClient):
    """Synchronous httpx client for OpenCloud LibreGraph API."""

    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"
    API_PREFIX = "/graph/v1.0"

    def __init__(self, base_url: str, credential: str, timeout: float = 30.0) -> None:
        if not base_url:
            from kctl_lib.exceptions import ConfigError

            raise ConfigError("No API URL configured. Run: kctl-opencloud config init")
        super().__init__(base_url=base_url, credential=credential, timeout=timeout)
        self._root_url = base_url.rstrip("/")

    @property
    def root_url(self) -> str:
        """Root URL without API prefix, for health checks and non-API endpoints."""
        return self._root_url

    @property
    def api_base_url(self) -> str:
        """Full API base URL including prefix, for @odata.id references."""
        return f"{self._root_url}{self.API_PREFIX}"

    def post(self, endpoint: str, data: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        return super().post(endpoint, json=data, **kwargs)

    def patch(self, endpoint: str, data: dict[str, Any], **kwargs: Any) -> Any:
        return super().patch(endpoint, json=data, **kwargs)

    def delete(self, endpoint: str, **kwargs: Any) -> Any:
        return super().delete(endpoint, **kwargs)

    def get_all(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Fetch all pages using OData @odata.nextLink pagination."""
        all_results: list[dict[str, Any]] = []
        data = self.get(endpoint, params=params)
        all_results.extend(data.get("value", []))
        page = 1
        while "@odata.nextLink" in data and page < 200:
            next_url = data["@odata.nextLink"]
            # nextLink is absolute — strip base URL to get relative endpoint
            if next_url.startswith(("http://", "https://")):
                from urllib.parse import urlparse

                parsed = urlparse(next_url)
                next_url = parsed.path
                if parsed.query:
                    next_url += f"?{parsed.query}"
            # Remove API_PREFIX if present since parent.get() adds it
            if next_url.startswith(self.API_PREFIX):
                next_url = next_url[len(self.API_PREFIX) :]
            data = self.get(next_url)
            all_results.extend(data.get("value", []))
            page += 1
        return all_results

    def check_health(self) -> int:
        """Check OCS capabilities endpoint for health."""
        try:
            r = httpx.get(
                f"{self.root_url}/ocs/v1.php/cloud/capabilities",
                timeout=5,
            )
            return r.status_code
        except httpx.HTTPError:
            return 0

    def get_version(self) -> str | None:
        """Get OpenCloud version from capabilities."""
        try:
            r = httpx.get(
                f"{self.root_url}/ocs/v1.php/cloud/capabilities",
                timeout=5,
            )
            if r.status_code == 200:
                data = r.json()
                return data.get("ocs", {}).get("data", {}).get("version", {}).get("string")
        except (httpx.HTTPError, ValueError):
            pass
        return None
