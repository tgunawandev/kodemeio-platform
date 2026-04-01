"""Tactical RMM API client — extends kctl-lib APIClient."""

from __future__ import annotations

from typing import Any

import httpx
from kctl_lib import ConfigError
from kctl_lib.api_client import APIClient


class RMMClient(APIClient):
    """Synchronous client for Tactical RMM REST API."""

    AUTH_HEADER = "X-API-KEY"
    AUTH_PREFIX = ""  # TRMM uses raw key, no "Bearer " prefix

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        if not base_url:
            raise ConfigError("No API URL configured. Run: kctl-rmm config init")

        # Ensure trailing slash is handled consistently
        base_url = base_url.rstrip("/")

        super().__init__(
            base_url=base_url,
            credential=api_key,
            timeout=timeout,
            retry_enabled=True,
            max_retries=max_retries,
        )

    def _ensure_trailing_slash(self, endpoint: str) -> str:
        """TRMM API requires trailing slashes on endpoints."""
        url = endpoint.lstrip("/")
        if not url.endswith("/") and "?" not in url:
            url += "/"
        return url

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
        return super()._request(method, self._ensure_trailing_slash(endpoint), **kwargs)

    def check_health(self) -> tuple[int, dict]:
        """Check API root endpoint (no auth needed)."""
        try:
            r = httpx.get(f"{self._base_url}/", timeout=10, follow_redirects=True)
            try:
                body = r.json()
            except Exception:
                body = {}
            return r.status_code, body
        except Exception:
            return 0, {}

    def check_auth(self) -> tuple[bool, str]:
        """Verify API key by calling /agents/ endpoint."""
        try:
            self.get("/agents/", params={"detail": "false"})
            return True, "authenticated"
        except Exception as e:
            return False, str(e)
