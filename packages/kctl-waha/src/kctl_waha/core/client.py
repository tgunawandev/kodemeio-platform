"""WAHA and Bridge API clients — uses kctl-lib base classes and exceptions."""

from __future__ import annotations

from typing import Any

import httpx
from kctl_lib.api_client import APIClient
from kctl_lib.exceptions import APIError, AuthenticationError
from kctl_lib.exceptions import ConnectionError as KctlConnectionError


class WahaClient(APIClient):
    """Synchronous httpx client for WAHA API.

    Uses X-Api-Key header (no prefix) and /api base path.
    """

    AUTH_HEADER = "X-Api-Key"
    AUTH_PREFIX = ""
    API_PREFIX = "/api"

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        if not base_url:
            from kctl_lib.exceptions import ConfigError

            raise ConfigError("No API URL configured. Run: kctl-waha config init")
        if not api_key:
            raise AuthenticationError("No API key configured. Run: kctl-waha config init")

        super().__init__(base_url=base_url, credential=api_key, timeout=timeout)
        self._root_url = base_url.rstrip("/")

    def get(self, endpoint: str, params: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        return super().get(endpoint, params=params, **kwargs)

    def post(self, endpoint: str, data: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        return super().post(endpoint, json=data, **kwargs)

    def put(self, endpoint: str, data: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        return super().put(endpoint, json=data, **kwargs)

    def delete(self, endpoint: str, **kwargs: Any) -> Any:
        return super().delete(endpoint, **kwargs)

    def check_health(self) -> dict[str, Any]:
        """Check WAHA health endpoint, returns response dict."""
        try:
            r = httpx.get(
                f"{self._root_url}/api/health",
                headers={"X-Api-Key": self._credential},
                timeout=5,
            )
            if r.status_code == 200:
                try:
                    return r.json()  # type: ignore[no-any-return]
                except Exception:  # noqa: BLE001
                    return {"status": "ok"}
            return {}
        except httpx.HTTPError:
            return {}


class BridgeClient:
    """Synchronous httpx client for WAHA Bridge sidecar (no auth)."""

    def __init__(self, base_url: str, timeout: float = 15.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=timeout,
            follow_redirects=True,
        )

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        url = endpoint.lstrip("/")
        try:
            resp = self._client.get(url, params=params)
        except httpx.ConnectError as e:
            raise KctlConnectionError(self._base_url, e) from e
        except httpx.HTTPError as e:
            raise KctlConnectionError(self._base_url, e) from e

        if resp.status_code >= 400:
            detail = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
            raise APIError(status_code=resp.status_code, detail=detail)
        if not resp.content:
            return {}
        return resp.json()  # type: ignore[no-any-return]

    def post(self, endpoint: str, data: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        url = endpoint.lstrip("/")
        try:
            resp = self._client.post(url, json=data)
        except httpx.ConnectError as e:
            raise KctlConnectionError(self._base_url, e) from e
        except httpx.HTTPError as e:
            raise KctlConnectionError(self._base_url, e) from e

        if resp.status_code >= 400:
            detail = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
            raise APIError(status_code=resp.status_code, detail=detail)
        if not resp.content:
            return {}
        return resp.json()  # type: ignore[no-any-return]

    def check_health(self) -> dict[str, Any]:
        """Check bridge health endpoint."""
        try:
            r = httpx.get(f"{self._base_url}/health", timeout=5)
            if r.status_code == 200:
                try:
                    return r.json()  # type: ignore[no-any-return]
                except Exception:  # noqa: BLE001
                    return {"status": "ok"}
            return {}
        except httpx.HTTPError:
            return {}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> BridgeClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
