"""GlitchTip API client — subclasses kctl-common APIClient.

GlitchTip uses Sentry-compatible REST API at /api/0/.
Auth: Token <token> from GlitchTip UI.
"""

from __future__ import annotations

from typing import Any

import httpx
from kctl_common.api_client import APIClient
from kctl_common.exceptions import AuthenticationError, ConfigError
from kctl_common.exceptions import ConnectionError as KctlConnectionError


class GlitchTipClient(APIClient):
    """Synchronous client for GlitchTip Sentry-compatible API."""

    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"
    API_PREFIX = "/api/0"

    def __init__(
        self,
        base_url: str = "",
        token: str = "",
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> None:
        if not base_url:
            raise ConfigError("No API URL configured. Run: kctl-glitchtip config init")
        if not token:
            raise AuthenticationError("No API token configured. Run: kctl-glitchtip config init")
        super().__init__(base_url=base_url, credential=token, timeout=timeout, **kwargs)
        # Store the original base_url (without API_PREFIX) for health checks
        self._original_base_url = base_url.rstrip("/")

    def _request_with_trailing_slash(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        """Ensure endpoints have a trailing slash (GlitchTip requirement)."""
        url = endpoint.lstrip("/")
        if not url.endswith("/") and "?" not in url:
            url += "/"
        return super()._request(method, url, **kwargs)

    # Override the core _request to add trailing slash
    def _request(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
        """Send request with trailing slash enforcement."""
        url = endpoint.lstrip("/")
        if not url.endswith("/") and "?" not in url:
            url += "/"
        return super()._request(method, url, **kwargs)

    # ------------------------------------------------------------------
    # GlitchTip-specific convenience methods
    # ------------------------------------------------------------------

    def get_list(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """GET that always returns a list (GlitchTip list endpoints return arrays)."""
        result = self.get(endpoint, params=params)
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "results" in result:
            return result["results"]
        return []

    def get_all(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Fetch all pages using cursor-based pagination."""
        all_results: list[dict[str, Any]] = []
        p = dict(params or {})
        p.setdefault("limit", 100)

        result = self.get(endpoint, params=p)
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "results" in result:
            all_results.extend(result["results"])
            return all_results
        return []

    def check_health(self) -> int:
        """Check health endpoint, returns HTTP status code."""
        try:
            r = httpx.get(f"{self._original_base_url}/_health/", timeout=5)
            return r.status_code
        except httpx.HTTPError:
            return 0

    def get_api_root(self) -> dict[str, Any]:
        """Get API root info."""
        result = self.get("/")
        return result if isinstance(result, dict) else {}
