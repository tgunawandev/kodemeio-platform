"""Mailcow API client — subclasses kctl-lib APIClient.

Mailcow API uses non-standard REST patterns:
- GET /api/v1/get/{resource}/{id_or_all}  — read
- POST /api/v1/add/{resource}             — create
- POST /api/v1/edit/{resource}            — update
- POST /api/v1/delete/{resource}          — delete

Auth: X-API-Key header (no prefix).
"""

from __future__ import annotations

from typing import Any

from kctl_lib.api_client import APIClient
from kctl_lib.exceptions import ConfigError


class MailcowClient(APIClient):
    """Synchronous httpx client for Mailcow API v1."""

    AUTH_HEADER = "X-API-Key"
    AUTH_PREFIX = ""  # Mailcow uses plain key, no "Bearer" prefix
    API_PREFIX = "/api/v1"

    def __init__(self, base_url: str, credential: str, timeout: float = 30.0) -> None:
        if not base_url:
            raise ConfigError("No API URL configured. Run: kctl-mailcow config init")
        super().__init__(base_url=base_url, credential=credential, timeout=timeout)
        # Store root URL for health checks
        self._root_url = base_url.rstrip("/")

    # -- Mailcow-specific CRUD wrappers --

    def mc_get(self, resource: str, identifier: str = "all") -> Any:
        """Mailcow-style GET: /api/v1/get/{resource}/{identifier}."""
        return self.get(f"get/{resource}/{identifier}")

    def mc_add(self, resource: str, data: dict[str, Any]) -> Any:
        """Mailcow-style ADD: POST /api/v1/add/{resource}."""
        return self.post(f"add/{resource}", json=data)

    def mc_edit(self, resource: str, data: dict[str, Any]) -> Any:
        """Mailcow-style EDIT: POST /api/v1/edit/{resource}."""
        return self.post(f"edit/{resource}", json=data)

    def mc_delete(self, resource: str, items: list[str]) -> Any:
        """Mailcow-style DELETE: POST /api/v1/delete/{resource} with items array."""
        return self.post(f"delete/{resource}", json=items)

    def check_health(self) -> tuple[bool, str]:
        """Check Mailcow API health by fetching container status."""
        try:
            self.mc_get("status/containers")
            return True, "ok"
        except Exception as e:
            return False, str(e)
