"""Dokploy API client, subclassing kctl-common's APIClient.

Provides Dokploy-specific auth (x-api-key header), retry support,
and health check functionality.
"""

from __future__ import annotations

from typing import Any

import httpx
from kctl_common.api_client import APIClient
from kctl_common.exceptions import ConfigError


class DokployClient(APIClient):
    """Synchronous httpx client for Dokploy API with retry support."""

    AUTH_HEADER = "x-api-key"
    AUTH_PREFIX = ""
    API_PREFIX = "/api"

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_base_delay: float = 2.0,
        retry_max_delay: float = 60.0,
        **kwargs: Any,
    ):
        if not base_url:
            raise ConfigError("No URL configured. Run: kctl-dokploy config init")

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

    def check_health(self) -> int:
        """Check health, returns HTTP status code."""
        try:
            r = httpx.get(f"{self.root_url}/", timeout=5)
            return r.status_code
        except httpx.HTTPError:
            return 0
