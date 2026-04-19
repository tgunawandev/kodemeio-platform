"""Async Dokploy API client — mirror of DokployClient for streaming subscriptions."""

from __future__ import annotations

from kctl_lib.async_api_client import AsyncAPIClient
from kctl_lib.config import get_service_config
from kctl_lib.exceptions import ConfigError


class AsyncDokployClient(AsyncAPIClient):
    """Async httpx client for Dokploy API — used for tRPC SSE subscriptions."""

    AUTH_HEADER = "x-api-key"
    AUTH_PREFIX = ""
    API_PREFIX = "/api"


def build_async_dokploy_client(profile: str | None) -> AsyncDokployClient:
    """Construct an AsyncDokployClient from the named kctl profile's dokploy config."""
    if not profile:
        raise ConfigError("No profile specified. Pass --profile/-p.")
    svc = get_service_config(profile, "dokploy")
    url = (svc.get("url") or "").rstrip("/")
    api_key = svc.get("api_key") or ""
    if not url or not api_key:
        raise ConfigError(f"Profile '{profile}' has no dokploy.url or .api_key")
    return AsyncDokployClient(base_url=url, credential=api_key)
