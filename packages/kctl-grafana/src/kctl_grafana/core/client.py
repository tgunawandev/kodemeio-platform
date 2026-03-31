"""Grafana API client, subclassing kctl-lib's APIClient.

Provides Grafana-specific auth (Bearer token), retry support,
and health check functionality.
"""

from __future__ import annotations

from typing import Any

import httpx
from kctl_lib.api_client import APIClient
from kctl_lib.exceptions import ConfigError


class GrafanaClient(APIClient):
    """Synchronous httpx client for Grafana API with retry support."""

    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"
    API_PREFIX = "/api"

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        org_id: int = 1,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_base_delay: float = 2.0,
        retry_max_delay: float = 60.0,
        **kwargs: Any,
    ):
        if not base_url:
            raise ConfigError("No URL configured. Run: kctl-grafana config init")

        self.org_id = org_id

        super().__init__(
            base_url=base_url,
            credential=api_key or "unset",
            timeout=timeout,
            retry_enabled=True,
            max_retries=max_retries,
            retry_base_delay=retry_base_delay,
            retry_max_delay=retry_max_delay,
            **kwargs,
        )

    @property
    def root_url(self) -> str:
        """Public accessor for the root URL (without /api)."""
        return self._base_url.rsplit("/api", 1)[0]

    def check_health(self) -> dict:
        """Check Grafana health endpoint. Returns health response dict."""
        try:
            r = httpx.get(f"{self.root_url}/api/health", timeout=5)
            return r.json()
        except httpx.HTTPError:
            return {"status": "error", "message": "unreachable"}

    def get_org(self) -> dict:
        """Get current organization info."""
        return self.get("/org")

    def get_version(self) -> str:
        """Get Grafana version from health endpoint."""
        health = self.check_health()
        return health.get("version", "unknown")
