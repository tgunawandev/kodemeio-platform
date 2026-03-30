"""Telegram gateway API client.

Subclasses APIClient from kctl-common with Telegram-specific methods.
"""

from __future__ import annotations

from typing import Any

import httpx
from kctl_common.api_client import APIClient
from kctl_common.exceptions import ConfigError


class TelegramClient(APIClient):
    """Synchronous client for Telegram gateway API v1."""

    AUTH_HEADER = "X-Api-Key"
    AUTH_PREFIX = ""
    API_PREFIX = "/api/v1"

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> None:
        if not base_url:
            raise ConfigError("No API URL configured. Run: kctl-telegram config init")
        if not api_key:
            raise ConfigError("No API key configured. Run: kctl-telegram config init")

        self._root_url = base_url.rstrip("/")
        super().__init__(base_url=base_url, credential=api_key, timeout=timeout, **kwargs)

    def get_all(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Fetch all pages and return combined results list."""
        all_results: list[dict[str, Any]] = []
        page = 1
        p = dict(params or {})
        p.setdefault("page_size", 100)
        while True:
            p["page"] = page
            data = self.get(endpoint, params=p)
            if isinstance(data, dict):
                all_results.extend(data.get("results", []))
                pagination = data.get("pagination", {})
                if not pagination.get("next"):
                    break
            else:
                break
            page += 1
            if page > 200:
                break
        return all_results

    def check_health(self) -> dict[str, Any]:
        """Check health endpoint, returns response dict."""
        try:
            r = httpx.get(f"{self._root_url}/api/v1/health", timeout=5)
            if r.status_code == 200:
                return r.json()  # type: ignore[no-any-return]
            return {"status": "unhealthy", "http_status": r.status_code}
        except httpx.HTTPError:
            return {"status": "unreachable"}

    def check_ready(self) -> dict[str, Any]:
        """Check readiness endpoint, returns response dict."""
        try:
            r = httpx.get(f"{self._root_url}/api/v1/ready", timeout=5)
            if r.status_code == 200:
                return r.json()  # type: ignore[no-any-return]
            return {"status": "not_ready", "http_status": r.status_code}
        except httpx.HTTPError:
            return {"status": "unreachable"}
