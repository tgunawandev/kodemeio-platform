"""Cloudflare API client — subclasses kctl-common APIClient."""

from __future__ import annotations

from typing import Any

import httpx
from kctl_common.api_client import APIClient
from kctl_common.exceptions import APIError, AuthenticationError, NotFoundError


class CloudflareClient(APIClient):
    """Synchronous client for Cloudflare API v4."""

    BASE_URL = "https://api.cloudflare.com/client/v4"
    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"

    def __init__(self, api_token: str = "", account_id: str = "", timeout: float = 30.0, **kwargs: Any):
        if not api_token:
            raise AuthenticationError("No API token configured. Run: kctl-cloudflare config init")
        super().__init__(credential=api_token, timeout=timeout, **kwargs)
        self._account_id = account_id

    def _unwrap_response(self, response: httpx.Response) -> Any:
        """Cloudflare wraps results in {success, result} envelope."""
        if not response.content:
            return {}
        data = response.json()
        if isinstance(data, dict) and "result" in data:
            if not data.get("success", True):
                errors = data.get("errors", [])
                detail = "; ".join(e.get("message", str(e)) for e in errors)
                raise APIError(status_code=response.status_code, detail=detail)
            return data["result"]
        return data

    def get_zone_id(self, zone_name: str) -> str:
        """Resolve zone name to zone ID."""
        result = self.get("/zones", params={"name": zone_name})
        if isinstance(result, list) and result:
            return result[0]["id"]
        raise NotFoundError("zone", zone_name)

    @property
    def account_id(self) -> str:
        return self._account_id

    def check_health(self) -> dict[str, Any]:
        return self.get("/user/tokens/verify")
