"""HTTP client for OpenClaw gateway API."""

from __future__ import annotations

from typing import Any

import httpx

from kctl_claw.core.exceptions import GatewayError


class GatewayClient:
    """HTTP client for the OpenClaw gateway runtime API."""

    def __init__(self, base_url: str, token: str, timeout: float = 30.0):
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Make an HTTP request, raising GatewayError on failure."""
        try:
            response = self._client.request(method, path, **kwargs)
        except (httpx.ConnectError, httpx.TimeoutException, ConnectionError) as e:
            raise GatewayError(message=f"Cannot connect to gateway at {self._base_url}: {e}") from e

        if response.status_code >= 400:
            raise GatewayError(
                status_code=response.status_code,
                message=response.text[:500],
            )

        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        return response.text

    def health(self) -> dict[str, Any]:
        """GET / — gateway health check."""
        return self._request("GET", "/")  # type: ignore[no-any-return]

    def get(self, path: str, **params: Any) -> Any:
        """Generic GET request."""
        return self._request("GET", path, params=params)

    def post(self, path: str, data: dict[str, Any] | None = None) -> Any:
        """Generic POST request."""
        return self._request("POST", path, json=data)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> GatewayClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
