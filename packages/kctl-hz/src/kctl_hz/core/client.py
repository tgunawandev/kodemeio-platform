"""Hetzner Cloud + DNS API clients built on kctl-common APIClient."""

from __future__ import annotations

from typing import Any

from kctl_common.api_client import APIClient


class HetznerCloudClient(APIClient):
    """Synchronous client for Hetzner Cloud API v1."""

    BASE_URL = "https://api.hetzner.cloud/v1"
    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"

    def __init__(self, credential: str = "", timeout: float = 30.0, **kwargs: Any) -> None:
        if not credential:
            from kctl_common.exceptions import ConfigError

            raise ConfigError("No Cloud API token configured. Run: kctl-hetzner config init")
        super().__init__(credential=credential, timeout=timeout, **kwargs)

    def get_all(self, endpoint: str, key: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Fetch all pages. Key is the response key (e.g. 'servers')."""
        all_results: list[dict[str, Any]] = []
        page = 1
        p: dict[str, Any] = dict(params or {})
        p["per_page"] = 50
        while True:
            p["page"] = page
            data = self.get(endpoint, params=p)
            all_results.extend(data.get(key, []))
            meta = data.get("meta", {}).get("pagination", {})
            if not meta.get("next_page"):
                break
            page = meta["next_page"]
            if page > 200:
                break
        return all_results


class HetznerDnsClient(APIClient):
    """Synchronous client for Hetzner DNS API v1."""

    BASE_URL = "https://dns.hetzner.com/api/v1"
    AUTH_HEADER = "Auth-API-Token"
    AUTH_PREFIX = ""

    def __init__(self, credential: str = "", timeout: float = 30.0, **kwargs: Any) -> None:
        if not credential:
            from kctl_common.exceptions import ConfigError

            raise ConfigError("No DNS API token configured. Run: kctl-hetzner config init")
        super().__init__(credential=credential, timeout=timeout, **kwargs)
